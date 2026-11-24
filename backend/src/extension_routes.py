from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from . import coverage, handoffs, lanes
from .contracts import FloorHourInput, Role
from .extension_contracts import BookingEnd, BookingInput, CoverageOrderInput, HandoffInput, LaneInput, LoadInput, Note
from .security import authenticate, permit
from .shift import lock_hour
from .storage import transaction

router = APIRouter()
Floor = Annotated[int, Query(ge=1, le=4)]
Hour = Annotated[FloorHourInput, Query()]
operator = permit(Role.OPERATOR)
steward = permit(Role.STEWARD)


@router.get('/coverage')
def get_coverage(query: Hour, _user=Depends(authenticate)):
    with transaction() as cur:
        return coverage.hour_overview(cur, query)


@router.post('/coverage', status_code=201)
def create_coverage(data: CoverageOrderInput, user=Depends(operator)):
    with transaction() as cur:
        hour = lock_hour(cur, data.floor, data.hour_start)
        return coverage.open_order(cur, hour, data, user['id'])


@router.post('/coverage/{key}/waive')
def waive_coverage(key: int, data: Note, user=Depends(operator)):
    with transaction() as cur:
        return coverage.waive_order(cur, key, data.note, user['id'])


@router.get('/lanes')
def get_lanes(floor: Floor, _user=Depends(authenticate)):
    with transaction() as cur:
        return lanes.list_lanes(cur, floor)


@router.post('/lanes', status_code=201)
def add_lane(data: LaneInput, user=Depends(operator)):
    with transaction() as cur:
        return lanes.create_lane(cur, data, user['id'])


@router.get('/lane-bookings')
def get_bookings(floor: Floor, _user=Depends(authenticate)):
    with transaction() as cur:
        return lanes.list_bookings(cur, floor)


@router.post('/lane-bookings', status_code=201)
def book_lane(data: BookingInput, user=Depends(operator)):
    with transaction() as cur:
        return lanes.book(cur, data, user['id'])


@router.post('/lane-bookings/{key}/use')
def use_lane(key: int, data: LoadInput, user=Depends(steward)):
    with transaction() as cur:
        return lanes.start_use(cur, key, data.moved_count, user['id'])


@router.post('/lane-bookings/{key}/end')
def end_lane(key: int, data: BookingEnd, user=Depends(authenticate)):
    role = Role.OPERATOR if data.action == 'cancel' else Role.STEWARD
    if user['role'] != role:
        raise HTTPException(403, '当前岗位无权执行此操作')
    with transaction() as cur:
        return lanes.end_booking(cur, key, data.action, user['id'])


@router.get('/handoffs')
def get_handoff(query: Hour, _user=Depends(authenticate)):
    with transaction() as cur:
        return handoffs.read_handoff(cur, query)


@router.post('/handoffs', status_code=201)
def publish_handoff(data: HandoffInput, user=Depends(operator)):
    with transaction() as cur:
        return handoffs.publish(cur, data, user['id'])


@router.post('/handoffs/{key}/ack')
def acknowledge_handoff(key: int, data: Note, user=Depends(steward)):
    with transaction() as cur:
        return handoffs.acknowledge(cur, key, data.note, user['id'])
