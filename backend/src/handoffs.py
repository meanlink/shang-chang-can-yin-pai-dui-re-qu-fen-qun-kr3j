import json

from fastapi import HTTPException

from . import recovery, surge
from .storage import audit


def find_hour(cur, query, *, lock=False):
    sql = 'SELECT * FROM floor_hours WHERE floor=%s AND hour_start=%s'
    cur.execute(sql + (' FOR UPDATE' if lock else ''), (query.floor, query.hour_start))
    return cur.fetchone()


def report_record(cur, hour_id):
    cur.execute('SELECT r.*,p.username AS publisher,u.username AS recipient FROM floor_handoffs r '
                'JOIN users p ON p.id=r.published_by LEFT JOIN users u ON u.id=r.received_by WHERE r.hour_id=%s',
                (hour_id,))
    record = cur.fetchone()
    if record:
        record['report'] = json.loads(record['report'])
    return record


def snapshot(cur, hour_id):
    cur.execute('SELECT h.zone_number,s.name AS anchor,t.id AS task_id,t.status,t.cleared_queue,t.close_note '
                'FROM hotspots h JOIN stores s ON s.id=h.anchor_store_id LEFT JOIN dispatch_tasks t ON t.hotspot_id=h.id '
                'WHERE h.hour_id=%s ORDER BY h.zone_number', (hour_id,))
    zones = cur.fetchall()
    cur.execute('SELECT p.kind,p.windows,p.median_queue,s.name,s.code,c.status AS coverage_status,c.waiver_reason '
                'FROM analysis_points p JOIN stores s ON s.id=p.store_id '
                'LEFT JOIN coverage_orders c ON c.hour_id=p.hour_id AND c.store_id=p.store_id '
                'WHERE p.hour_id=%s ORDER BY s.code', (hour_id,))
    points = cur.fetchall()
    cur.execute('SELECT l.name AS lane_name,b.moved_count,b.task_id '
                'FROM lane_bookings b JOIN queue_lanes l ON l.id=b.lane_id '
                'JOIN dispatch_tasks t ON t.id=b.task_id JOIN hotspots h ON h.id=t.hotspot_id '
                "WHERE h.hour_id=%s AND b.status='released' ORDER BY b.id", (hour_id,))
    lane_uses = cur.fetchall()
    watch = [row | {'median_queue': float(row['median_queue']) if row['median_queue'] is not None else None}
             for row in points if row['kind'] in ('insufficient', 'noise')]
    responses = [{'id': row['id'], 'anchor': row['anchor'], 'status': row['status'],
                  'reported_queue': row['reported_queue'], 'release_queue': row['release_queue']}
                 for row in surge.for_hour(cur, hour_id)]
    followups = [{'id': row['id'], 'name': row['name'], 'status': row['status'], 'issue_note': row['issue_note'],
                  'checks': len(row['checks'])} for row in recovery.for_hour(cur, hour_id)]
    return {'surges': responses, 'recoveries': followups, 'entries': len(points), 'observed_windows': sum(row['windows'] for row in points),
            'missing_windows': sum(4 - row['windows'] for row in points), 'zones': zones, 'confirmed': sum(row['task_id'] is not None for row in zones), 'watch': watch,
            'lane_uses': lane_uses, 'moved': sum(row['moved_count'] for row in lane_uses),
            'pending': sum(row['status'] != 'closed' for row in zones)}


def read_handoff(cur, query):
    hour = find_hour(cur, query)
    if not hour or hour['status'] != 'ready':
        return {'state': 'waiting_analysis', 'record': None, 'report': None}
    record = report_record(cur, hour['id'])
    if record:
        return {'state': 'received' if record['received_by'] else 'published', 'record': record, 'report': record['report']}
    report = snapshot(cur, hour['id'])
    return {'state': 'waiting_dispatch' if report['pending'] else 'publishable', 'record': None, 'report': report}


def publish(cur, request, actor):
    hour = find_hour(cur, request, lock=True)
    if not hour or hour['status'] != 'ready':
        raise HTTPException(409, '请先完成该楼层小时的热区分析')
    if report_record(cur, hour['id']):
        raise HTTPException(409, '该楼层小时已发布交接简报')
    report = snapshot(cur, hour['id'])
    if report['pending']:
        raise HTTPException(409, '仍有热区待确认或疏导未结案，不能发布简报')
    cur.execute('INSERT INTO floor_handoffs(hour_id,report,published_by,publish_note) VALUES(%s,%s,%s,%s)',
                (hour['id'], json.dumps(report, ensure_ascii=False), actor, request.note))
    key = cur.lastrowid
    audit(cur, actor, 'handoff.published', key)
    return {'id': key, 'state': 'published'}


def acknowledge(cur, key, note, actor):
    cur.execute('UPDATE floor_handoffs SET received_by=%s,receive_note=%s,received_at=CURRENT_TIMESTAMP '
                'WHERE id=%s AND received_by IS NULL', (actor, note, key))
    if not cur.rowcount:
        cur.execute('SELECT id FROM floor_handoffs WHERE id=%s', (key,))
        if not cur.fetchone():
            raise HTTPException(404, '交接简报不存在')
        raise HTTPException(409, '该交接简报已签收')
    audit(cur, actor, 'handoff.received', key)
    return {'id': key, 'state': 'received'}
