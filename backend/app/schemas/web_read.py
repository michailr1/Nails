from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class WebCalendarBooking(BaseModel):
    booking_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    service_name: str
    starts_at: datetime
    ends_at: datetime
    status: str
    price_amount: Decimal
    currency: str


class WebCalendarResponse(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    bookings: list[WebCalendarBooking]


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
