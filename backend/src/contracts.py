from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Role(StrEnum):
    OBSERVER = 'observer'
    OPERATOR = 'operator'
    STEWARD = 'steward'


class PointKind(StrEnum):
    INSUFFICIENT = 'insufficient'
    BELOW_THRESHOLD = 'below_threshold'
    NOISE = 'noise'
    CORE = 'core'
    BORDER = 'border'


class TaskStatus(StrEnum):
    ASSIGNED = 'assigned'
    ACTIVE = 'active'
    CLOSED = 'closed'


class SignIn(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=120)


class StoreInput(BaseModel):
    code: str = Field(pattern=r'^[A-Z0-9-]{2,16}$')
    name: str = Field(min_length=1, max_length=60)
    floor: int = Field(ge=1, le=4)
    x: int = Field(ge=0, le=120)
    y: int = Field(ge=0, le=64)
    staging_point: str = Field(min_length=1, max_length=80)

    @field_validator('name', 'staging_point', mode='before')
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


def validate_clock(value, interval):
    if value.tzinfo is not None or value.minute % interval or value.second or value.microsecond:
        raise ValueError(f'请输入上海本地时间，按 {interval} 分钟对齐')
    return value


class FloorHourInput(BaseModel):
    floor: int = Field(ge=1, le=4)
    hour_start: datetime

    @field_validator('hour_start')
    @classmethod
    def hour_boundary(cls, value):
        return validate_clock(value, 60)


class RelocationInput(BaseModel):
    floor: int = Field(ge=1, le=4)
    x: int = Field(ge=0, le=120)
    y: int = Field(ge=0, le=64)
    staging_point: str = Field(min_length=1, max_length=80)
    effective_hour: datetime

    @field_validator('staging_point', mode='before')
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('effective_hour')
    @classmethod
    def hour_boundary(cls, value):
        return validate_clock(value, 60)


class ObservationInput(BaseModel):
    store_id: int = Field(gt=0)
    window_start: datetime
    queue_count: int = Field(ge=0, le=300)

    @field_validator('window_start')
    @classmethod
    def window_boundary(cls, value):
        return validate_clock(value, 15)


class Clearance(BaseModel):
    cleared_queue: int = Field(ge=0, le=300)
    close_note: str = Field(min_length=4, max_length=160)

    @field_validator('close_note', mode='before')
    @classmethod
    def normalize_note(cls, value):
        return value.strip() if isinstance(value, str) else value
