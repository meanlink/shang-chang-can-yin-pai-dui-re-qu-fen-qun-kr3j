from datetime import datetime

from src.security import password_hash
from src.storage import transaction

STORES = [
    ('F3-301', '山岚汤面', 3, 24, 24, '东廊 E1 黄线'),
    ('F3-302', '禾野煲仔', 3, 31, 24, '东廊 E2 黄线'),
    ('F3-303', '南屿米粉', 3, 40, 24, '东廊 E2 黄线'),
    ('F3-304', '小满甜品', 3, 56, 24, '东廊 E3 等候区'),
    ('F3-305', '桥边烤肉', 3, 98, 47, '西廊 W1 等候区'),
    ('F3-306', '晴茶快闪', 3, 33, 33, '东廊 E2 黄线'),
    ('F3-307', '青禾便当', 3, 78, 18, '中庭南侧等候区'),
    ('F2-208', '小岸咖啡', 2, 31, 24, '二层西梯侧'),
]
COUNTS = {
    'F3-301': [12, 15, 17, 14], 'F3-302': [21, 24, 20, 23],
    'F3-303': [10, 13, 15, 12], 'F3-304': [9, 10, 12, 11],
    'F3-305': [13, 14, 16, 15], 'F3-306': [20, 22],
    'F3-307': [2, 4, 4, 6], 'F2-208': [11, 12, 13, 12],
}


def seed():
    with transaction() as cur:
        for username, role in [('patrol', 'observer'), ('floorlead', 'operator'), ('guide', 'steward')]:
            cur.execute('SELECT id FROM users WHERE username=%s', (username,))
            if not cur.fetchone():
                cur.execute('INSERT INTO users(username,password_hash,role) VALUES (%s,%s,%s) '
                            'ON DUPLICATE KEY UPDATE id=id', (username, password_hash('changhe-demo'), role))
        cur.execute("SELECT id FROM users WHERE username='patrol'")
        observer = cur.fetchone()['id']
        cur.executemany('INSERT INTO stores(code,name,floor,x,y,staging_point) VALUES (%s,%s,%s,%s,%s,%s) '
                        'ON DUPLICATE KEY UPDATE id=id', STORES)
        for code, values in COUNTS.items():
            cur.execute('SELECT id,floor FROM stores WHERE code=%s', (code,))
            store = cur.fetchone()
            if not store:
                continue
            start = datetime(2026, 11, 21, 12)
            cur.execute('INSERT INTO floor_hours(floor,hour_start) VALUES (%s,%s) '
                        'ON DUPLICATE KEY UPDATE id=id', (store['floor'], start))
            cur.execute('SELECT id,status FROM floor_hours WHERE floor=%s AND hour_start=%s FOR UPDATE',
                        (store['floor'], start))
            hour = cur.fetchone()
            if hour['status'] != 'collecting':
                continue
            cur.executemany('INSERT INTO observations(hour_id,store_id,window_start,queue_count,recorded_by) '
                            'VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE id=id',
                            [(hour['id'], store['id'], start.replace(minute=index * 15), count, observer)
                             for index, count in enumerate(values)])
        for table in ('users', 'stores', 'floor_hours', 'observations', 'hotspots', 'dispatch_tasks'):
            cur.execute(f'SELECT COUNT(*) AS total FROM {table}')
            print(f"{table}={cur.fetchone()['total']}")


if __name__ == '__main__':
    seed()
