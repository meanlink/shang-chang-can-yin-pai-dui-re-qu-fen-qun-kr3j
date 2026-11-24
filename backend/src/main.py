import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pymysql import IntegrityError, OperationalError

from scripts.seed_demo import seed

from .contracts import Clearance, FloorHourInput, ObservationInput, Role, SignIn, StoreInput
from .extension_routes import router as extension_router
from .peak_routes import router as peak_router
from .security import authenticate, login, permit
from .shift import confirm_zone, move_task, queue_shift, read_map, record_window
from .storage import audit, cache, transaction

logger = logging.getLogger('uvicorn.error')


@asynccontextmanager
async def lifespan(_app):
    migrations = Path(__file__).resolve().parents[1] / 'migrations'
    with transaction() as cur:
        for migration in sorted(migrations.glob('0*.sql')):
            for statement in migration.read_text(encoding='utf-8').split(';'):
                if statement.strip():
                    cur.execute(statement)
    if os.getenv('SEED_DEMO', 'true').lower() == 'true':
        try:
            seed()
        except Exception:
            logger.exception('Demo seed failed')
    yield


app = FastAPI(title='长河广场 · 餐饮排队热区', lifespan=lifespan)
app.include_router(extension_router)
app.include_router(peak_router)


@app.middleware('http')
async def request_trace(request, call_next):
    request_id = uuid4().hex[:12]
    started = monotonic()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    if request.method != 'GET' or response.status_code >= 400:
        logger.info('%s %s %s %s %.0fms', request_id, request.method, request.url.path,
                    response.status_code, (monotonic() - started) * 1000)
    return response


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.exception_handler(OperationalError)
async def database_unavailable(_request, error):
    logger.warning('Database operation failed: %s', error.args[0])
    return JSONResponse(status_code=503, content={'detail': '数据服务暂时不可用，可稍后重试'})


@app.get('/health')
def health():
    with transaction() as cur:
        cur.execute('SELECT 1')
    cache.ping()
    return {'status': 'ok'}


@app.post('/auth/login')
def sign_in(data: SignIn):
    with transaction() as cur:
        result = login(data.username, data.password, cur)
        audit(cur, result['user']['id'], 'auth.login', data.username)
    return result


@app.get('/stores')
def get_stores(floor: int = Query(ge=1, le=4), _user=Depends(authenticate)):
    with transaction() as cur:
        cur.execute('SELECT * FROM stores WHERE floor=%s ORDER BY code', (floor,))
        return cur.fetchall()


@app.post('/stores', status_code=201)
def create_store(data: StoreInput, user=Depends(permit(Role.OPERATOR))):
    with transaction() as cur:
        try:
            cur.execute('INSERT INTO stores(code,name,floor,x,y,staging_point) VALUES (%s,%s,%s,%s,%s,%s)',
                        (data.code, data.name, data.floor, data.x, data.y, data.staging_point))
        except IntegrityError as error:
            if error.args[0] != 1062:
                raise
            raise HTTPException(409, '门店编号或楼层坐标已登记') from None
        store_id = cur.lastrowid
        audit(cur, user['id'], 'store.created', store_id)
    return {'id': store_id}


@app.get('/observations')
def get_windows(query: Annotated[FloorHourInput, Query()], _user=Depends(authenticate)):
    with transaction() as cur:
        cur.execute('SELECT * FROM floor_hours WHERE floor=%s AND hour_start=%s', (query.floor, query.hour_start))
        hour = cur.fetchone()
        cur.execute('SELECT id,code,name FROM stores WHERE floor=%s ORDER BY code', (query.floor,))
        stores = cur.fetchall()
        observations = []
        if hour:
            cur.execute('SELECT o.*,u.username FROM observations o JOIN users u ON u.id=o.recorded_by '
                        'WHERE hour_id=%s ORDER BY window_start', (hour['id'],))
            observations = cur.fetchall()
    return {'hour': hour, 'stores': stores, 'observations': observations}


@app.post('/observations')
def create_window(data: ObservationInput, user=Depends(permit(Role.OBSERVER))):
    with transaction() as cur:
        return record_window(cur, data, user)


@app.post('/analyses', status_code=202)
def run_analysis(data: FloorHourInput, user=Depends(permit(Role.OPERATOR))):
    with transaction() as cur:
        return queue_shift(cur, data, user)


@app.get('/analyses/{hour_id}')
def get_analysis(hour_id: int, _user=Depends(authenticate)):
    with transaction() as cur:
        return read_map(cur, hour_id)


@app.post('/hotspots/{hotspot_id}/confirm')
def approve_hotspot(hotspot_id: int, user=Depends(permit(Role.OPERATOR))):
    with transaction() as cur:
        return confirm_zone(cur, hotspot_id, user)


@app.get('/tasks')
def get_tasks(floor: int = Query(ge=1, le=4), _user=Depends(authenticate)):
    with transaction() as cur:
        cur.execute('SELECT t.*, h.zone_number, f.hour_start, s.name AS anchor, u.username AS handler '
                    'FROM dispatch_tasks t JOIN hotspots h ON h.id=t.hotspot_id '
                    'JOIN floor_hours f ON f.id=h.hour_id JOIN stores s ON s.id=h.anchor_store_id '
                    'LEFT JOIN users u ON u.id=t.handled_by WHERE f.floor=%s ORDER BY f.hour_start DESC,t.id', (floor,))
        return cur.fetchall()


@app.post('/tasks/{task_id}/claim')
def claim_task(task_id: int, user=Depends(permit(Role.STEWARD))):
    with transaction() as cur:
        return move_task(cur, task_id, user)


@app.post('/tasks/{task_id}/close')
def close_task(task_id: int, data: Clearance, user=Depends(permit(Role.STEWARD))):
    with transaction() as cur:
        return move_task(cur, task_id, user, data)
