from datetime import timedelta

from fastapi import HTTPException
from pymysql import IntegrityError

from .storage import audit


def list_lanes(cur, floor):
    cur.execute('SELECT * FROM queue_lanes WHERE floor=%s ORDER BY name,id', (floor,))
    return cur.fetchall()


def list_bookings(cur, floor):
    cur.execute('SELECT b.id,b.task_id,b.lane_id,b.slot_start,b.seats,b.status,b.moved_count,b.guide_id, '
                "l.name AS lane_name,l.capacity,t.status AS task_status,t.handled_by,s.name AS anchor, "
                "SUM(CASE WHEN b.status IN ('booked','in_use') THEN b.seats ELSE 0 END) "
                "OVER (PARTITION BY b.lane_id,b.slot_start) AS occupied "
                'FROM lane_bookings b JOIN queue_lanes l ON l.id=b.lane_id JOIN dispatch_tasks t ON t.id=b.task_id '
                'JOIN hotspots h ON h.id=t.hotspot_id JOIN stores s ON s.id=h.anchor_store_id '
                "WHERE l.floor=%s ORDER BY (b.status IN ('booked','in_use')) DESC,b.slot_start DESC,b.id DESC", (floor,))
    return cur.fetchall()


def create_lane(cur, data, actor):
    try:
        cur.execute('INSERT INTO queue_lanes(floor,name,capacity) VALUES(%s,%s,%s)', (data.floor, data.name, data.capacity))
    except IntegrityError as error:
        if error.args[0] != 1062:
            raise
        raise HTTPException(409, '该楼层已有同名等候线') from None
    key = cur.lastrowid
    audit(cur, actor, 'lane.created', key)
    return {'id': key}


def lock_task(cur, key):
    cur.execute('SELECT status,handled_by,hotspot_id FROM dispatch_tasks WHERE id=%s FOR UPDATE', (key,))
    task = cur.fetchone()
    if not task:
        raise HTTPException(404, '疏导任务不存在')
    return task


def book(cur, data, actor):
    task = lock_task(cur, data.task_id)
    if task['status'] == 'closed':
        raise HTTPException(409, '已结案疏导单不能预留等候线')
    cur.execute('SELECT f.floor,f.hour_start FROM floor_hours f JOIN hotspots h ON h.hour_id=f.id WHERE h.id=%s',
                (task['hotspot_id'],))
    hour = cur.fetchone()
    elapsed = data.slot_start - hour['hour_start']
    if not timedelta(hours=1) <= elapsed < timedelta(hours=3):
        raise HTTPException(422, '等候线时段须在观测小时结束后的两小时内')
    cur.execute('SELECT * FROM queue_lanes WHERE id=%s FOR UPDATE', (data.lane_id,))
    lane = cur.fetchone()
    if not lane or lane['floor'] != hour['floor']:
        raise HTTPException(422, '等候线须位于疏导任务所在楼层')
    cur.execute('SELECT id FROM lane_bookings WHERE blocking_task_id=%s', (data.task_id,))
    if cur.fetchone():
        raise HTTPException(409, '该任务已有有效等候线预留')
    cur.execute("SELECT COALESCE(SUM(seats),0) AS used FROM lane_bookings WHERE lane_id=%s AND slot_start=%s "
                "AND status IN ('booked','in_use')", (data.lane_id, data.slot_start))
    remaining = lane['capacity'] - int(cur.fetchone()['used'])
    if data.seats > remaining:
        raise HTTPException(409, f'该时段仅余 {remaining} 个名额')
    cur.execute('INSERT INTO lane_bookings(task_id,lane_id,slot_start,seats,booked_by) VALUES(%s,%s,%s,%s,%s)',
                (data.task_id, data.lane_id, data.slot_start, data.seats, actor))
    key = cur.lastrowid
    audit(cur, actor, 'lane.booked', key)
    return {'id': key, 'status': 'booked'}


def lock_booking(cur, key):
    cur.execute('SELECT task_id FROM lane_bookings WHERE id=%s', (key,))
    reference = cur.fetchone()
    if not reference:
        raise HTTPException(404, '等候线预留不存在')
    task = lock_task(cur, reference['task_id'])
    cur.execute('SELECT * FROM lane_bookings WHERE id=%s FOR UPDATE', (key,))
    return cur.fetchone(), task


def start_use(cur, key, count, actor):
    booking, task = lock_booking(cur, key)
    if task['handled_by'] != actor:
        raise HTTPException(403, '仅认领该疏导单的现场人员可登记使用')
    if task['status'] != 'active' or booking['status'] != 'booked':
        raise HTTPException(409, '预留有效且疏导单处理中才可登记入线')
    if count > booking['seats']:
        raise HTTPException(422, '实入人数不能超过预留容量')
    cur.execute("UPDATE lane_bookings SET status='in_use',moved_count=%s,guide_id=%s WHERE id=%s", (count, actor, key))
    audit(cur, actor, 'lane.in_use', key)
    return {'id': key, 'status': 'in_use'}


def end_booking(cur, key, action, actor):
    booking, task = lock_booking(cur, key)
    if action == 'release' and task['handled_by'] != actor:
        raise HTTPException(403, '仅认领该疏导单的现场人员可释放等候线')
    expected, target = ('in_use', 'released') if action == 'release' else ('booked', 'cancelled')
    if booking['status'] != expected:
        raise HTTPException(409, '该预留当前状态不允许此操作')
    cur.execute('UPDATE lane_bookings SET status=%s WHERE id=%s', (target, key))
    audit(cur, actor, f'lane.{target}', key)
    return {'id': key, 'status': target}


def require_free_lane(cur, task_id):
    cur.execute("SELECT 1 FROM lane_bookings WHERE task_id=%s AND status IN ('booked','in_use') LIMIT 1", (task_id,))
    if cur.fetchone():
        raise HTTPException(409, '结案前须释放等候线或由运营取消未使用的预留')
