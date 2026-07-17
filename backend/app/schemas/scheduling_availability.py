from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.scheduling import AvailabilitySummary


class AvailabilityBookingConflict(BaseModel):
    client_public_name: str
    service_name: str
    starts_at: datetime
    ends_at: datetime
    reserved_starts_at: datetime
    reserved_ends_at: datetime


class AvailabilityPreviewDay(BaseModel):
    day: date
    weekday_iso: int
    availability_known: bool
    current_availability: list[AvailabilitySummary]
    proposed_availability: list[AvailabilitySummary]
    changed: bool
    can_apply: bool
    conflicts: list[AvailabilityBookingConflict]


class AvailabilityPreviewResponse(BaseModel):
    days: list[AvailabilityPreviewDay]
