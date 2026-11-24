from fastapi import HTTPException

from .contracts import TaskStatus
from .coverage import record_progress, require_resolved_orders
from .density import QUEUE_THRESHOLD
from .lanes import lock_task, require_free_lane
from .relocation import location_at, locations_at, roster
from .surge import require_clear as require_clear_surge
from .storage import audit


def lock_hour(cur, floor, start):
    cur.execute('INSERT INTO floor_hours(floor,hour_start) VALUES (%s,%s) '
                'ON DUPLICATE KEY UPDATE id=id', (floor, start))
    cur.execute('SELECT * FROM floor_hours WHERE floor=%s AND hour_start=%s FOR UPDATE', (floor, start))
    return cur.fetchone()


def record_window(cur, data, user):
    # Lock the store before the floor hour, matching relocation and coverage order.
    cur.execute('SELECT id FROM stores WHERE id=%s FOR UPDATE', (data.store_id,))
    if not cur.fetchone():
        raise HTTPException(404, '门店不存在')
    # A late window belongs to the floor the store was on when it was measured.
    spot = location_at(cur, data.store_id, data.window_start)
    hour = lock_hour(cur, spot['floor'], data.window_start.replace(minute=0))
    if hour['status'] != 'collecting':
        raise HTTPException(409, '本轮分析已封存，无法变更观测窗口')
    cur.execute('SELECT id, queue_count FROM observations WHERE store_id=%s AND window_start=%s',
                (data.store_id, data.window_start))
    existing = cur.fetchone()
    if existing:
        if existing['queue_count'] != data.queue_count:
            raise HTTPException(409, '该门店窗口已有不同人数，请核实原始记录')
        return {'id': existing['id'], 'duplicate': True}
    cur.execute('INSERT INTO observations(hour_id,store_id,window_start,queue_count,recorded_by) '
                'VALUES (%s,%s,%s,%s,%s)',
                (hour['id'], data.store_id, data.window_start, data.queue_count, user['id']))
    window_id = cur.lastrowid
    record_progress(cur, hour['id'], data.store_id, user['id'])
    audit(cur, user['id'], 'window.recorded', window_id)
    return {'id': window_id, 'duplicate': False}


def queue_shift(cur, data, user):
    hour = lock_hour(cur, data.floor, data.hour_start)
    if hour['status'] not in ('collecting', 'failed'):
        return {'id': hour['id'], 'status': hour['status']}
    cur.execute('SELECT 1 FROM observations WHERE hour_id=%s LIMIT 1', (hour['id'],))
    if not cur.fetchone():
        raise HTTPException(409, '该楼层小时没有观测，请先提交窗口')
    # Freeze the floor roster together with the window data. Stores registered later cannot join this analysis.
    if hour['status'] == 'collecting':
        require_resolved_orders(cur, hour['id'])
        members = roster(cur, data.floor, data.hour_start)
        cur.executemany("INSERT INTO analysis_points(hour_id,store_id,windows,kind) VALUES (%s,%s,0,'insufficient')",
                        [(hour['id'], store_id) for store_id in members])
    cur.execute("UPDATE floor_hours SET status='queued' WHERE id=%s", (hour['id'],))
    audit(cur, user['id'], 'shift.queued', hour['id'])
    return {'id': hour['id'], 'status': 'queued'}


def read_map(cur, hour_id):
    cur.execute('SELECT * FROM floor_hours WHERE id=%s', (hour_id,))
    hour = cur.fetchone()
    if not hour:
        raise HTTPException(404, '楼层小时不存在')
    if hour['status'] != 'ready':
        return {'hour': hour, 'points': [], 'hotspots': []}
    cur.execute('SELECT p.*,s.code,s.name,h.zone_number FROM analysis_points p '
                'JOIN stores s ON s.id=p.store_id LEFT JOIN hotspots h ON h.id=p.hotspot_id '
                'WHERE p.hour_id=%s ORDER BY s.code', (hour_id,))
    points = cur.fetchall()
    # Positions and staging points stay as they were when the hour was sealed.
    sealed = locations_at(cur, [point['store_id'] for point in points], hour['hour_start'])
    for point in points:
        point.update(sealed[point['store_id']])
    cur.execute('SELECT h.*,s.name AS anchor,t.id AS task_id FROM hotspots h '
                'JOIN stores s ON s.id=h.anchor_store_id LEFT JOIN dispatch_tasks t ON t.hotspot_id=h.id '
                'WHERE h.hour_id=%s ORDER BY h.zone_number', (hour_id,))
    zones = cur.fetchall()
    anchors = locations_at(cur, [zone['anchor_store_id'] for zone in zones], hour['hour_start'])
    for zone in zones:
        zone['staging_point'] = anchors[zone['anchor_store_id']]['staging_point']
    return {'hour': hour, 'points': points, 'hotspots': zones}


def confirm_zone(cur, hotspot_id, user):
    cur.execute('SELECT status,hour_id,anchor_store_id FROM hotspots WHERE id=%s FOR UPDATE', (hotspot_id,))
    hotspot = cur.fetchone()
    if not hotspot:
        raise HTTPException(404, '热区不存在')
    if hotspot['status'] == 'confirmed':
        cur.execute('SELECT id FROM dispatch_tasks WHERE hotspot_id=%s', (hotspot_id,))
        return {'task_id': cur.fetchone()['id'], 'duplicate': True}
    cur.execute('SELECT hour_start FROM floor_hours WHERE id=%s', (hotspot['hour_id'],))
    hour_start = cur.fetchone()['hour_start']
    # Dispatch to the staging point the anchor had when the hour was sealed.
    staging_point = location_at(cur, hotspot['anchor_store_id'], hour_start)['staging_point']
    cur.execute("UPDATE hotspots SET status='confirmed',confirmed_by=%s WHERE id=%s", (user['id'], hotspot_id))
    cur.execute('INSERT INTO dispatch_tasks(hotspot_id,staging_point,instruction) VALUES (%s,%s,%s)',
                (hotspot_id, staging_point, '将队尾移至临时等候线，保持主通道畅通并复测队列'))
    task_id = cur.lastrowid
    audit(cur, user['id'], 'hotspot.confirmed', hotspot_id)
    audit(cur, user['id'], 'task.assigned', task_id)
    return {'task_id': task_id, 'duplicate': False}


def move_task(cur, task_id, user, clearance=None):
    task = lock_task(cur, task_id)
    if clearance is None:
        if task['status'] != TaskStatus.ASSIGNED:
            raise HTTPException(409, '只有待接单任务可认领')
        cur.execute("UPDATE dispatch_tasks SET status='active',handled_by=%s WHERE id=%s", (user['id'], task_id))
        audit(cur, user['id'], 'task.claimed', task_id)
        return {'status': TaskStatus.ACTIVE}
    if task['status'] != TaskStatus.ACTIVE or task['handled_by'] != user['id']:
        raise HTTPException(409, '需由认领此任务的现场疏导员结案')
    if clearance.cleared_queue >= QUEUE_THRESHOLD:
        raise HTTPException(409, f'队尾复测仍达到 {QUEUE_THRESHOLD} 人，请继续疏导')
    require_free_lane(cur, task_id)
    require_clear_surge(cur, task_id)
    cur.execute("UPDATE dispatch_tasks SET status='closed',cleared_queue=%s,close_note=%s WHERE id=%s",
                (clearance.cleared_queue, clearance.close_note, task_id))
    audit(cur, user['id'], 'task.closed', task_id)
    return {'status': TaskStatus.CLOSED}
