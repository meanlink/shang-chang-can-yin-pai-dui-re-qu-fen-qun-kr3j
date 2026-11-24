from fastapi import APIRouter, Depends

from . import recovery, recovery_checks, surge
from .extension_contracts import Note
from .extension_routes import Hour, operator, steward
from .handoffs import find_hour
from .peak_contracts import RecoveryCheck, RecoveryIssue, RecoverySlot, SurgePlan, SurgeRelease
from .security import authenticate
from .storage import transaction

router = APIRouter()


@router.get('/surges')
def get_surges(query: Hour, _user=Depends(authenticate)):
    with transaction() as cur:
        hour = find_hour(cur, query)
        if not hour or hour['status'] != 'ready':
            return {'responses': [], 'tasks': []}
        return {'responses': surge.for_hour(cur, hour['id']), 'tasks': surge.eligible_tasks(cur, hour['id'])}


@router.post('/surges', status_code=201)
def create_surge(data: SurgePlan, user=Depends(operator)):
    with transaction() as cur:
        return surge.plan(cur, data, user['id'])


@router.post('/surges/{key}/activate')
def activate_surge(key: int, user=Depends(steward)):
    with transaction() as cur:
        return surge.activate(cur, key, user['id'])


@router.post('/surges/{key}/release')
def release_surge(key: int, data: SurgeRelease, user=Depends(steward)):
    with transaction() as cur:
        return surge.finish(cur, key, user['id'], data.note, data.queue_count)


@router.post('/surges/{key}/cancel')
def cancel_surge(key: int, data: Note, user=Depends(operator)):
    with transaction() as cur:
        return surge.finish(cur, key, user['id'], data.note)


@router.get('/recoveries')
def get_recoveries(query: Hour, _user=Depends(authenticate)):
    with transaction() as cur:
        hour = find_hour(cur, query)
        if not hour or hour['status'] != 'ready':
            return {'cases': [], 'sources': []}
        return {'cases': recovery.for_hour(cur, hour['id']), 'sources': recovery.sources(cur, hour['id'])}


@router.post('/recoveries', status_code=201)
def create_recovery(data: RecoveryIssue, user=Depends(operator)):
    with transaction() as cur:
        return recovery.open_case(cur, find_hour(cur, data, lock=True), data, user['id'])


@router.post('/recoveries/{key}/action')
def correct_recovery(key: int, data: RecoverySlot, user=Depends(steward)):
    with transaction() as cur:
        return recovery.apply_action(cur, key, data, user['id'])


@router.post('/recoveries/{key}/checks', status_code=201)
def check_recovery(key: int, data: RecoveryCheck, user=Depends(steward)):
    with transaction() as cur:
        return recovery_checks.record(cur, recovery.lock_case(cur, key), data, user['id'])


@router.post('/recoveries/{key}/close')
def close_recovery(key: int, data: Note, user=Depends(operator)):
    with transaction() as cur:
        return recovery.close(cur, key, data.note, user['id'])
