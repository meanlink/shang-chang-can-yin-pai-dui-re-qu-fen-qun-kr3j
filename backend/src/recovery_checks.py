from datetime import timedelta

from fastapi import HTTPException

from .density import QUEUE_THRESHOLD
from .storage import audit

CHECK_INTERVAL = timedelta(minutes=15)


def checks_for_hour(cur, hour_id):
    cur.execute('SELECT c.*,u.username FROM recovery_checks c JOIN tenant_recoveries r ON r.id=c.case_id '
                'JOIN users u ON u.id=c.recorded_by WHERE r.hour_id=%s ORDER BY c.case_id,c.slot_start', (hour_id,))
    grouped = {}
    for row in cur.fetchall():
        grouped.setdefault(row['case_id'], []).append(row)
    return grouped


def can_close(checks):
    if len(checks) < 2:
        return False
    previous, latest = checks[-2:]
    return (latest['slot_start'] - previous['slot_start'] == CHECK_INTERVAL
            and max(previous['queue_count'], latest['queue_count']) < QUEUE_THRESHOLD)


def latest_checks(cur, key):
    cur.execute('SELECT slot_start,queue_count FROM recovery_checks WHERE case_id=%s ORDER BY slot_start DESC LIMIT 2', (key,))
    return list(reversed(cur.fetchall()))


def record(cur, case, data, actor):
    if case['status'] != 'monitoring':
        raise HTTPException(409, '只有执行改进措施后的工单可以记录复查')
    if data.slot_start < case['action_slot'] + CHECK_INTERVAL:
        raise HTTPException(422, '首次复查须在措施执行至少 15 分钟后')
    checks = latest_checks(cur, case['id'])
    if checks and data.slot_start <= checks[-1]['slot_start']:
        raise HTTPException(409, '复查窗口须晚于上一条记录')
    cur.execute('INSERT INTO recovery_checks(case_id,slot_start,queue_count,note,recorded_by) VALUES (%s,%s,%s,%s,%s)',
                (case['id'], data.slot_start, data.queue_count, data.note, actor))
    evidence = checks + [{'slot_start': data.slot_start, 'queue_count': data.queue_count}]
    audit(cur, actor, 'recovery.checked', case['id'])
    return {'id': case['id'], 'close_ready': can_close(evidence)}
