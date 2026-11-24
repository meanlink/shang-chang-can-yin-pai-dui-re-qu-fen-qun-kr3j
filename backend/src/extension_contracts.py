from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .contracts import FloorHourInput, validate_clock


class CoverageOrderInput(FloorHourInput):
    model_config = ConfigDict(extra='forbid')
    store_id: int = Field(gt=0)


class Note(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    note: str = Field(min_length=8, max_length=200)


class LaneInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    floor: int = Field(ge=1, le=4)
    name: str = Field(min_length=2, max_length=60)
    capacity: int = Field(ge=1, le=150)


class BookingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: int = Field(gt=0)
    lane_id: int = Field(gt=0)
    slot_start: datetime
    seats: int = Field(ge=1, le=150)

    @field_validator('slot_start')
    @classmethod
    def aligned(cls, value):
        return validate_clock(value, 15)


class LoadInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    moved_count: int = Field(ge=1, le=150)


class BookingEnd(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['release', 'cancel']


class HandoffInput(Note, FloorHourInput):
    pass
