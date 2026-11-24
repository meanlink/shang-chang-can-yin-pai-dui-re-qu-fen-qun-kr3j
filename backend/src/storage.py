import os
from contextlib import contextmanager

import pymysql
from redis import Redis

cache = Redis(host=os.getenv('REDIS_HOST', 'redis'), socket_timeout=2)


@contextmanager
def transaction():
    connection = pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'db'), port=int(os.getenv('MYSQL_PORT', '3306')),
        user='queue_ops', password=os.environ['MYSQL_PASSWORD'], database='queue_ops',
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
        init_command='SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED',
    )
    try:
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def audit(cur, user_id, action, target):
    cur.execute('INSERT INTO audit_events(actor_id, action, target) VALUES (%s,%s,%s)',
                (user_id, action, str(target)))
