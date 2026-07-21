from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.scheduling import ServicePriceTypeValue


class WebCalendarBooking(BaseModel):
    booking_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    service_name: str
    addon_names: list[str]
    starts_at: datetime
    ends_at: datetime
    status: str
    price_amount: Decimal | None
    currency: str
    price_type: ServicePriceTypeValue
    price_min_amount: Decimal | None
    price_max_amount: Decimal | None
    price_unit: str | None
    price_confirmed: bool
    duration_minutes: int


class WebCalendarResponse(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    bookings: list[WebCalendarBooking]


class WebBookingCreateResponse(BaseModel):
    booking: WebCalendarBooking
    created: bool


class WebClientCard(BaseModel):
    client_id: uuid.UUID
    public_name: str
    phone: str | None
    contact_channel: str | None
    birthday: date | None
    notes: str | None
    nail_skin_notes: str | None
    sensitivity_notes: str | None
    style_preferences: str | None
    communication_preferences: str | None
    profile_status: str
    updated_at: datetime


class WebClientListResponse(BaseModel):
    clients: list[WebClientCard]


class WebClientCreateRequest(BaseModel):
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


class WebClientCreateResponse(BaseModel):
    client: WebClientCard
    created: bool
    contact_added: bool = False
