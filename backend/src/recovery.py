from datetime import timedelta

from fastapi import HTTPException

from . import recovery_checks
from .storage import audit


def sources(cur, hour_id):
    cur.execute('SELECT p.store_id,p.kind,p.median_queue,s.name,s.code,r.id AS surge_id '
                'FROM analysis_points p JOIN stores s ON s.id=p.store_id '
                'LEFT JOIN dispatch_tasks t ON t.hotspot_id=p.hotspot_id '
                "LEFT JOIN surge_responses r ON r.task_id=t.id AND r.status='resolved' "
                'WHERE p.hour_id=%s AND NOT EXISTS (SELECT 1 FROM tenant_recoveries c '
                'WHERE c.hour_id=p.hour_id AND c.store_id=p.store_id) '
                "AND (p.kind='noise' OR (p.kind IN ('core','border') AND r.id IS NOT NULL)) ORDER BY s.code,r.id DESC",
                (hour_id,))
    return cur.fetchall()


def for_hour(cur, hour_id):
    cur.execute('SELECT c.*,s.name,s.code FROM tenant_recoveries c JOIN stores s ON s.id=c.store_id '
                'WHERE c.hour_id=%s ORDER BY c.id DESC', (hour_id,))
    cases = cur.fetchall()
    checks = recovery_checks.checks_for_hour(cur, hour_id)
    for case in cases:
        case['checks'] = checks.get(case['id'], [])
        case['close_ready'] = case['status'] == 'monitoring' and recovery_checks.can_close(case['checks'])
    return cases


def open_case(cur, hour, data, actor):
    if not hour or hour['status'] != 'ready':
        raise HTTPException(409, '请先完成观测小时的热区分析')
    cur.execute('SELECT p.kind,p.median_queue,r.id AS surge_id FROM analysis_points p '
                'LEFT JOIN dispatch_tasks t ON t.hotspot_id=p.hotspot_id '
                "LEFT JOIN surge_responses r ON r.task_id=t.id AND r.status='resolved' AND r.id=%s "
                'WHERE p.hour_id=%s AND p.store_id=%s', (data.surge_id, hour['id'], data.store_id))
    point = cur.fetchone()
    valid_noise = point and point['kind'] == 'noise' and data.surge_id is None
    valid_member = point and point['kind'] in ('core', 'border') and point['surge_id'] is not None
    if not valid_noise and not valid_member:
        raise HTTPException(422, '请选择封存图的孤立长队，或已解除控流的热区成员')
    cur.execute('SELECT id FROM tenant_recoveries WHERE hour_id=%s AND store_id=%s', (hour['id'], data.store_id))
    if cur.fetchone():
        raise HTTPException(409, '该门店本小时已有服务恢复工单')
    cur.execute('INSERT INTO tenant_recoveries(hour_id,store_id,surge_id,issue_note,source_queue,opened_by) '
                'VALUES (%s,%s,%s,%s,%s,%s)',
                (hour['id'], data.store_id, data.surge_id, data.note, point['median_queue'], actor))
    key = cur.lastrowid
    audit(cur, actor, 'recovery.opened', key)
    return {'id': key, 'status': 'open'}


def lock_case(cur, key):
    cur.execute('SELECT hour_id FROM tenant_recoveries WHERE id=%s', (key,))
    case = cur.fetchone()
    if not case:
        raise HTTPException(404, '服务恢复工单不存在')
    # Recovery edits and handoff publication share the floor-hour lock.
    cur.execute('SELECT hour_start FROM floor_hours WHERE id=%s FOR UPDATE', (case['hour_id'],))
    hour = cur.fetchone()
    cur.execute('SELECT * FROM tenant_recoveries WHERE id=%s FOR UPDATE', (key,))
    return cur.fetchone() | hour


def apply_action(cur, key, data, actor):
    case = lock_case(cur, key)
    if case['status'] != 'open':
        raise HTTPException(409, '该工单已登记改进措施')
    if data.slot_start < case['hour_start'] + timedelta(hours=1):
        raise HTTPException(422, '措施执行时间须在封存观测小时结束后')
    cur.execute("UPDATE tenant_recoveries SET status='monitoring',action_note=%s,action_slot=%s,action_by=%s WHERE id=%s",
                (data.note, data.slot_start, actor, key))
    audit(cur, actor, 'recovery.monitoring', key)
    return {'id': key, 'status': 'monitoring'}


def close(cur, key, note, actor):
    case = lock_case(cur, key)
    if case['status'] != 'monitoring' or not recovery_checks.can_close(recovery_checks.latest_checks(cur, key)):
        raise HTTPException(409, '最近两个连续的 15 分钟复查窗口均少于 8 人后，才可结案')
    cur.execute("UPDATE tenant_recoveries SET status='closed',close_note=%s,closed_by=%s,closed_at=NOW() WHERE id=%s",
                (note, actor, key))
    audit(cur, actor, 'recovery.closed', key)
    return {'id': key, 'status': 'closed'}
