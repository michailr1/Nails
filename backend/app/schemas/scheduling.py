from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
