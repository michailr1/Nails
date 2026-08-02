from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.scheduling import AvailabilitySummary


class WebScheduleDay(BaseModel):
    day: date
    weekday_iso: int
    availability_known: bool
    availability: list[AvailabilitySummary]
    booking_count: int


class WebScheduleResponse(BaseModel):
    timezone: str
    date_from: date
    date_to: date
    days: list[WebScheduleDay]


class WebScheduleRangeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date
    max_days: int = Field(default=31, ge=1, le=31)

    @model_validator(mode="after")
    def validate_range(self) -> WebScheduleRangeQuery:
        if self.date_to < self.date_from:
            raise ValueError("date_to_before_date_from")
        if (self.date_to - self.date_from).days + 1 > self.max_days:
            raise ValueError("schedule_range_too_large")
        return self
