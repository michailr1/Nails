from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FinalizationDigestOwnersResponse(BaseModel):
    telegram_user_ids: list[int]


class FinalizationDigestClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_day: date


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


class FinalizationDigestLongAbsentClient(BaseModel):
    client_name: str
    last_visit_date: date
    days_since_last_visit: int = Field(ge=0)
    visits_count: int = Field(ge=2)


class FinalizationDigestClaimResponse(BaseModel):
    claimed: bool
    claim_id: uuid.UUID | None = None
    local_day: date
    bookings: list[FinalizationDigestBooking]
    long_absent_clients: list[FinalizationDigestLongAbsentClient] = Field(
        default_factory=list
    )


class FinalizationDigestAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: uuid.UUID
    sent: bool


class FinalizationDigestAckResponse(BaseModel):
    changed: bool
    sent: bool
    bookings_count: int = Field(ge=0)
