from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import BookingStatus


class ServiceSummary(BaseModel):
    id: uuid.UUID
    public_name: str
    public_description: str | None
    price_amount: Decimal
    currency: str
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int


class ServiceListResponse(BaseModel):
    services: list[ServiceSummary]


class ClientSummary(BaseModel):
    id: uuid.UUID
    public_name: str
    phone: str | None


class ClientLookupResponse(BaseModel):
    found: bool
    client: ClientSummary | None = None


class ClientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("public_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("public_name must not be empty")
        return candidate

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = " ".join(value.split())
        return candidate or None


class ClientCreateResponse(BaseModel):
    client: ClientSummary
    created: bool
    contact_added: bool = False


class AvailabilitySummary(BaseModel):
    start_time: time | None
    end_time: time | None
    is_available: bool
    note: str | None


class DayBookingSummary(BaseModel):
    id: uuid.UUID
    client_public_name: str
    service_name: str
    starts_at: datetime
    ends_at: datetime
    reserved_starts_at: datetime
    reserved_ends_at: datetime
    status: BookingStatus
    price_amount: Decimal
    currency: str
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int


class DayViewResponse(BaseModel):
    day: date
    timezone: str
    weekday_iso: int
    availability_known: bool
    availability: list[AvailabilitySummary]
    bookings: list[DayBookingSummary]


class FreeSlotsResponse(BaseModel):
    day: date
    timezone: str
    weekday_iso: int
    availability_known: bool
    is_working: bool
    step_minutes: int
    service: ServiceSummary
    starts_at: list[datetime]


class DateResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["absolute", "relative_days", "weekday"]
    day: date | None = None
    offset_days: int | None = Field(default=None, ge=-366, le=366)
    weekday_iso: int | None = Field(default=None, ge=1, le=7)
    occurrence: Literal["nearest_future", "current_week", "next_week"] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> DateResolveRequest:
        if self.kind == "absolute":
            if self.day is None or any(
                value is not None
                for value in (self.offset_days, self.weekday_iso, self.occurrence)
            ):
                raise ValueError("absolute resolution requires only day")
            return self
        if self.kind == "relative_days":
            if self.offset_days is None or any(
                value is not None for value in (self.day, self.weekday_iso, self.occurrence)
            ):
                raise ValueError("relative_days resolution requires only offset_days")
            return self
        if self.weekday_iso is None or self.occurrence is None or any(
            value is not None for value in (self.day, self.offset_days)
        ):
            raise ValueError("weekday resolution requires weekday_iso and occurrence")
        return self


class DateResolveResponse(BaseModel):
    timezone: str
    today: date
    today_weekday_iso: int
    day: date
    weekday_iso: int
    is_past: bool
    kind: Literal["absolute", "relative_days", "weekday"]
    occurrence: Literal["nearest_future", "current_week", "next_week"] | None


class AvailabilityIntervalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_interval(self) -> AvailabilityIntervalInput:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class AvailabilityDayReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: date
    state: Literal["available", "unavailable", "unknown"]
    intervals: list[AvailabilityIntervalInput] = Field(default_factory=list, max_length=4)
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_state(self) -> AvailabilityDayReplace:
        if self.state == "available":
            if not self.intervals:
                raise ValueError("available day requires at least one interval")
            self.intervals.sort(key=lambda interval: interval.start_time)
            for previous, current in zip(self.intervals, self.intervals[1:], strict=False):
                if current.start_time < previous.end_time:
                    raise ValueError("availability intervals must not overlap")
            return self
        if self.intervals:
            raise ValueError("unavailable or unknown day cannot contain intervals")
        if self.state == "unknown" and self.note is not None:
            raise ValueError("unknown day cannot contain a note")
        return self


class AvailabilityReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: list[AvailabilityDayReplace] = Field(min_length=1, max_length=31)

    @model_validator(mode="after")
    def unique_days(self) -> AvailabilityReplaceRequest:
        values = [item.day for item in self.days]
        if len(values) != len(set(values)):
            raise ValueError("availability days must be unique")
        self.days.sort(key=lambda item: item.day)
        return self


class AvailabilityDayResult(BaseModel):
    day: date
    weekday_iso: int
    availability_known: bool
    availability: list[AvailabilitySummary]
    changed: bool


class AvailabilityReplaceResponse(BaseModel):
    days: list[AvailabilityDayResult]


class BookingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_public_name: str = Field(min_length=1, max_length=160)
    service_name: str = Field(min_length=1, max_length=160)
    starts_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("client_public_name", "service_name", "idempotency_key")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("value must not be empty")
        return candidate

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset")
        return value


class BookingCreateResponse(BaseModel):
    booking: DayBookingSummary
    created: bool
