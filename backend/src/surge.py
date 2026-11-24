from fastapi import HTTPException

from . import surge_policy
from .lanes import lock_task
from .storage import audit


def for_hour(cur, hour_id):
    cur.execute('SELECT r.*,h.zone_number,s.name AS anchor,t.handled_by FROM surge_responses r '
                'JOIN dispatch_tasks t ON t.id=r.task_id JOIN hotspots h ON h.id=t.hotspot_id '
                'JOIN stores s ON s.id=h.anchor_store_id WHERE h.hour_id=%s ORDER BY r.id DESC', (hour_id,))
    return cur.fetchall()


def eligible_tasks(cur, hour_id):
    cur.execute('SELECT t.id,h.zone_number,s.name AS anchor,p.median_queue '
                'FROM dispatch_tasks t JOIN hotspots h ON h.id=t.hotspot_id '
                'JOIN stores s ON s.id=h.anchor_store_id JOIN analysis_points p '
                'ON p.hour_id=h.hour_id AND p.store_id=h.anchor_store_id '
                "WHERE h.hour_id=%s AND t.status='active' AND NOT EXISTS (SELECT 1 FROM surge_responses r "
                "WHERE r.task_id=t.id AND r.status IN ('planned','active')) ORDER BY h.zone_number", (hour_id,))
    return [row | surge_policy.thresholds(row['median_queue']) for row in cur.fetchall()]


def require_clear(cur, task_id):
    cur.execute("SELECT id FROM surge_responses WHERE task_id=%s AND status IN ('planned','active')", (task_id,))
    if cur.fetchone():
        raise HTTPException(409, '请先处理该疏导单的临时控流方案')


def plan(cur, data, actor):
    task = lock_task(cur, data.task_id)
    if task['status'] != 'active':
        raise HTTPException(409, '现场疏导员认领任务后才能启动临时控流')
    require_clear(cur, data.task_id)
    cur.execute('SELECT p.median_queue FROM hotspots h JOIN analysis_points p '
                'ON p.hour_id=h.hour_id AND p.store_id=h.anchor_store_id WHERE h.id=%s', (task['hotspot_id'],))
    median = cur.fetchone()['median_queue']
    limit = surge_policy.require_trigger(data.reported_queue, median)
    cur.execute('INSERT INTO surge_responses(task_id,response_mode,baseline_queue,reported_queue,release_limit,plan_note,opened_by) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (data.task_id, data.response_mode, median, data.reported_queue, limit, data.note, actor))
    key = cur.lastrowid
    audit(cur, actor, 'surge.planned', key)
    return {'id': key, 'status': 'planned'}


def locked_response(cur, key):
    cur.execute('SELECT task_id FROM surge_responses WHERE id=%s', (key,))
    response = cur.fetchone()
    if not response:
        raise HTTPException(404, '临时控流方案不存在')
    task = lock_task(cur, response['task_id'])
    cur.execute('SELECT status,release_limit FROM surge_responses WHERE id=%s FOR UPDATE', (key,))
    return cur.fetchone(), task


def activate(cur, key, actor):
    response, task = locked_response(cur, key)
    if task['handled_by'] != actor:
        raise HTTPException(403, '请由认领该疏导单的现场疏导员执行')
    if response['status'] != 'planned':
        raise HTTPException(409, '只有待执行的方案可以启动控流')
    cur.execute("UPDATE surge_responses SET status='active',activated_by=%s,activated_at=NOW() WHERE id=%s", (actor, key))
    audit(cur, actor, 'surge.activated', key)
    return {'id': key, 'status': 'active'}


def finish(cur, key, actor, note, queue_count=None):
    response, task = locked_response(cur, key)
    if queue_count is None:
        if response['status'] != 'planned':
            raise HTTPException(409, '只可撤销现场尚未启动的方案')
        outcome = 'cancelled'
    else:
        if task['handled_by'] != actor:
            raise HTTPException(403, '请由认领该疏导单的现场疏导员执行')
        if response['status'] != 'active':
            raise HTTPException(409, '请先启动控流再提交复测')
        surge_policy.require_release(queue_count, response['release_limit'])
        outcome = 'resolved'
    cur.execute('UPDATE surge_responses SET status=%s,release_queue=%s,outcome_note=%s,ended_by=%s,ended_at=NOW() WHERE id=%s',
                (outcome, queue_count, note, actor, key))
    audit(cur, actor, f'surge.{outcome}', key)
    return {'id': key, 'status': outcome}
