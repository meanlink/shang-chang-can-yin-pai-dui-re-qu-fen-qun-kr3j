import logging
import time
from pathlib import Path

from .density import map_floor
from .storage import audit, cache, transaction


def analyze(cur, hour_id):
    cur.execute('SELECT s.* FROM analysis_points p JOIN stores s ON s.id=p.store_id '
                'WHERE p.hour_id=%s', (hour_id,))
    stores = cur.fetchall()
    cur.execute('SELECT store_id,queue_count FROM observations WHERE hour_id=%s', (hour_id,))
    points, anchors = map_floor(stores, cur.fetchall())
    hotspots = {}
    for zone, anchor_id in anchors.items():
        cur.execute('INSERT INTO hotspots(hour_id,zone_number,anchor_store_id) VALUES (%s,%s,%s)',
                    (hour_id, zone, anchor_id))
        hotspots[zone] = cur.lastrowid
    cur.executemany('UPDATE analysis_points SET windows=%s, median_queue=%s, kind=%s, hotspot_id=%s '
                    'WHERE hour_id=%s AND store_id=%s',
                    [(p['windows'], p['median_queue'], p['kind'], hotspots.get(p['zone']), hour_id, store_id)
                     for store_id, p in points.items()])
    cur.execute("UPDATE floor_hours SET status='ready',generated_at=NOW() WHERE id=%s", (hour_id,))
    audit(cur, None, 'shift.analyzed', hour_id)


def process_next():
    with transaction() as cur:
        cur.execute("SELECT id FROM floor_hours WHERE status='queued' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED")
        hour = cur.fetchone()
        if not hour:
            return
        cur.execute('SAVEPOINT analysis_start')
        try:
            analyze(cur, hour['id'])
        except Exception:
            logging.exception('Analysis failed for floor hour %s', hour['id'])
            cur.execute('ROLLBACK TO SAVEPOINT analysis_start')
            cur.execute("UPDATE floor_hours SET status='failed' WHERE id=%s", (hour['id'],))
            audit(cur, None, 'shift.failed', hour['id'])


if __name__ == '__main__':
    while True:
        try:
            process_next()
            cache.setex('mall:worker', 15, 'ready')
            Path('/runtime/worker.tick').touch()
        except Exception:
            logging.exception('Worker iteration failed')
        time.sleep(1)
