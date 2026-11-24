from datetime import datetime

from fastapi import HTTPException

from .storage import audit

FAR_FUTURE = datetime(9999, 12, 31)


def locations_at(cur, store_ids, when):
    """Effective floor, coordinates and staging point of each store at a moment.

    The base store row applies until the first relocation; each relocation then
    holds from its effective hour until the next one. Relocations are immutable,
    so a sealed hour always replays with the coordinates it was sealed with.
    """
    ids = list(store_ids)
    if not ids:
        return {}
    marks = ','.join(['%s'] * len(ids))
    cur.execute(f'SELECT id,floor,x,y,staging_point FROM stores WHERE id IN ({marks})', ids)
    located = {row['id']: {key: row[key] for key in ('floor', 'x', 'y', 'staging_point')} for row in cur.fetchall()}
    cur.execute(f'SELECT store_id,floor,x,y,staging_point FROM store_relocations '
                f'WHERE store_id IN ({marks}) AND effective_hour<=%s ORDER BY effective_hour,id', (*ids, when))
    for row in cur.fetchall():
        located[row['store_id']] = {key: row[key] for key in ('floor', 'x', 'y', 'staging_point')}
    return located


def location_at(cur, store_id, when):
    return locations_at(cur, [store_id], when).get(store_id)


def roster(cur, floor, when):
    """Ids of the stores located on the floor at the given moment."""
    cur.execute('SELECT id FROM stores')
    located = locations_at(cur, [row['id'] for row in cur.fetchall()], when)
    return sorted(store_id for store_id, spot in located.items() if spot['floor'] == floor)


def for_stores(cur, store_ids):
    """Relocation history of the given stores, oldest first."""
    ids = list(store_ids)
    if not ids:
        return {}
    marks = ','.join(['%s'] * len(ids))
    cur.execute(f'SELECT * FROM store_relocations WHERE store_id IN ({marks}) ORDER BY effective_hour,id', ids)
    moves = {}
    for row in cur.fetchall():
        moves.setdefault(row['store_id'], []).append(row)
    return moves


def register(cur, store_id, data, actor):
    # The store row lock serializes the move against sampling, coverage orders and
    # other relocations of the same store submitted at the same time.
    cur.execute('SELECT id FROM stores WHERE id=%s FOR UPDATE', (store_id,))
    if not cur.fetchone():
        raise HTTPException(404, '门店不存在')
    when = data.effective_hour
    cur.execute('SELECT id FROM store_relocations WHERE store_id=%s AND effective_hour=%s', (store_id, when))
    if cur.fetchone():
        raise HTTPException(409, '该生效整点已有搬迁登记')
    current = location_at(cur, store_id, when)
    if current['floor'] == data.floor:
        raise HTTPException(422, '新楼层须与生效时所在楼层不同')
    cur.execute('SELECT effective_hour FROM store_relocations WHERE store_id=%s AND effective_hour>%s '
                'ORDER BY effective_hour LIMIT 1', (store_id, when))
    later = cur.fetchone()
    horizon = later['effective_hour'] if later else FAR_FUTURE
    # The move re-attributes the hours [when, horizon) from the current floor to the
    # new one. Anything already recorded in that window would change ownership.
    cur.execute('SELECT 1 FROM observations WHERE store_id=%s AND window_start>=%s AND window_start<%s LIMIT 1',
                (store_id, when, horizon))
    if cur.fetchone():
        raise HTTPException(409, '搬迁会改动已有观测的归属，已退回')
    cur.execute('SELECT 1 FROM coverage_orders c JOIN floor_hours f ON f.id=c.hour_id '
                'WHERE c.store_id=%s AND f.hour_start>=%s AND f.hour_start<%s LIMIT 1', (store_id, when, horizon))
    if cur.fetchone():
        raise HTTPException(409, '搬迁会改动补采任务的归属，已退回')
    # Lock the affected floor hours in a fixed order. A concurrent seal either
    # commits first (and is seen here) or waits for this move and re-reads the roster.
    cur.execute('SELECT id,status FROM floor_hours WHERE floor IN (%s,%s) AND hour_start>=%s AND hour_start<%s '
                'ORDER BY hour_start,floor,id FOR UPDATE', (current['floor'], data.floor, when, horizon))
    if any(row['status'] != 'collecting' for row in cur.fetchall()):
        raise HTTPException(409, '搬迁会改动楼层的封存名册，已退回')
    cur.execute('INSERT INTO store_relocations(store_id,effective_hour,floor,x,y,staging_point,registered_by) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (store_id, when, data.floor, data.x, data.y, data.staging_point, actor))
    key = cur.lastrowid
    audit(cur, actor, 'store.relocated', key)
    return {'id': key}
