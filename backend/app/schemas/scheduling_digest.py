from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FinalizationDigestClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_day: date
    now: datetime

    @field_validator("now")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now must include a timezone offset")
        return value


class FinalizationDigestBooking(BaseModel):
    client_public_name: str
    service_name: str
    addon_names: list[str]
    starts_at: datetime
    ends_at: datetime
    price_type: Literal["fixed", "range", "per_unit", "on_request"]
    price_amount: Decimal | None
    price_min_amount: Decimal | None
    price_max_amount: Decimal | None
    price_unit: str | None
    currency: str


class FinalizationDigestClaimResponse(BaseModel):
    claimed: bool
    claim_id: uuid.UUID | None = None
    local_day: date
    bookings: list[FinalizationDigestBooking]


class FinalizationDigestAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: uuid.UUID
    sent: bool


class FinalizationDigestAckResponse(BaseModel):
    changed: bool
    sent: bool
    bookings_count: int = Field(ge=0)
