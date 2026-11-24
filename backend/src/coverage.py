from fastapi import HTTPException

from .storage import audit

MIN_WINDOWS = 3


def hour_overview(cur, query):
    cur.execute('SELECT id,status FROM floor_hours WHERE floor=%s AND hour_start=%s', (query.floor, query.hour_start))
    hour = cur.fetchone()
    hour_id = hour['id'] if hour else None
    status = hour['status'] if hour else 'collecting'
    cur.execute('SELECT s.id,s.code,s.name,c.id AS order_id,c.status AS order_status,c.waiver_reason, '
                'o.window_start FROM stores s LEFT JOIN coverage_orders c ON c.store_id=s.id AND c.hour_id=%s '
                'LEFT JOIN observations o ON o.store_id=s.id AND o.hour_id=%s WHERE s.floor=%s '
                "AND (%s='collecting' OR EXISTS (SELECT 1 FROM analysis_points p WHERE p.store_id=s.id AND p.hour_id=%s)) "
                'ORDER BY s.code,o.window_start', (hour_id, hour_id, query.floor, status, hour_id))
    stores = {}
    for row in cur.fetchall():
        windows = stores.setdefault(row['id'], row | {'recorded_minutes': []})['recorded_minutes']
        if row['window_start'] is not None:
            windows.append(row['window_start'].minute)
    for store in stores.values():
        store.pop('window_start')
        store['missing_minutes'] = sorted({0, 15, 30, 45} - set(store['recorded_minutes']))
        store['needed'] = max(0, MIN_WINDOWS - len(store['recorded_minutes']))
    return {'hour_status': status, 'stores': list(stores.values())}


def open_order(cur, hour, data, actor):
    if hour['status'] != 'collecting':
        raise HTTPException(409, '只能给尚未封存的小时安排补采')
    cur.execute('SELECT id FROM stores WHERE id=%s AND floor=%s', (data.store_id, data.floor))
    if not cur.fetchone():
        raise HTTPException(404, '该楼层没有此门店')
    cur.execute('SELECT COUNT(*) AS total FROM observations WHERE hour_id=%s AND store_id=%s', (hour['id'], data.store_id))
    if cur.fetchone()['total'] >= MIN_WINDOWS:
        raise HTTPException(409, '该门店已达到三个观测窗口')
    cur.execute('SELECT id FROM coverage_orders WHERE hour_id=%s AND store_id=%s', (hour['id'], data.store_id))
    if cur.fetchone():
        raise HTTPException(409, '该门店本小时已有补采记录')
    cur.execute('INSERT INTO coverage_orders(hour_id,store_id,assigned_by) VALUES(%s,%s,%s)',
                (hour['id'], data.store_id, actor))
    key = cur.lastrowid
    audit(cur, actor, 'coverage.opened', key)
    return {'id': key, 'status': 'open'}


def record_progress(cur, hour_id, store_id, actor):
    cur.execute('SELECT id FROM coverage_orders WHERE hour_id=%s AND store_id=%s AND status=\'open\'', (hour_id, store_id))
    order = cur.fetchone()
    if not order:
        return
    cur.execute('SELECT COUNT(*) AS total FROM observations WHERE hour_id=%s AND store_id=%s', (hour_id, store_id))
    if cur.fetchone()['total'] >= MIN_WINDOWS:
        cur.execute("UPDATE coverage_orders SET status='complete',resolved_by=%s,resolved_at=CURRENT_TIMESTAMP WHERE id=%s",
                    (actor, order['id']))
        audit(cur, actor, 'coverage.completed', order['id'])


def require_resolved_orders(cur, hour_id):
    cur.execute("SELECT 1 FROM coverage_orders WHERE hour_id=%s AND status='open' LIMIT 1", (hour_id,))
    if cur.fetchone():
        raise HTTPException(409, '仍有补采任务待完成，补采达标或登记豁免后再封存')


def waive_order(cur, key, note, actor):
    cur.execute('SELECT hour_id FROM coverage_orders WHERE id=%s', (key,))
    order = cur.fetchone()
    if not order:
        raise HTTPException(404, '补采任务不存在')
    # Match the hour-first locking order used by sampling and sealing.
    cur.execute('SELECT status FROM floor_hours WHERE id=%s FOR UPDATE', (order['hour_id'],))
    if cur.fetchone()['status'] != 'collecting':
        raise HTTPException(409, '该小时已封存')
    cur.execute("UPDATE coverage_orders SET status='waived',resolved_by=%s,resolved_at=CURRENT_TIMESTAMP,waiver_reason=%s "
                "WHERE id=%s AND status='open'", (actor, note, key))
    if not cur.rowcount:
        raise HTTPException(409, '只有待补采任务可以豁免')
    audit(cur, actor, 'coverage.waived', key)
    return {'id': key, 'status': 'waived'}
