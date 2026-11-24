from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from .contracts import FloorHourInput, validate_clock
from .extension_contracts import Note


class SurgePlan(Note):
    task_id: int = Field(gt=0)
    response_mode: Literal['meter_entry', 'stagger_pickup']
    reported_queue: int = Field(ge=0, le=300)


class SurgeRelease(Note):
    queue_count: int = Field(ge=0, le=300)


class RecoveryIssue(Note, FloorHourInput):
    store_id: int = Field(gt=0)
    surge_id: int | None = Field(default=None, gt=0)


class RecoverySlot(Note):
    slot_start: datetime

    @field_validator('slot_start')
    @classmethod
    def quarter_hour(cls, value):
        return validate_clock(value, 15)


class RecoveryCheck(RecoverySlot):
    queue_count: int = Field(ge=0, le=300)
