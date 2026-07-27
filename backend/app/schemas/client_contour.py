from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.scheduling import ServiceKindValue, ServicePriceTypeValue


class ClientEntryState(StrEnum):
    no_binding = "no_binding"
    choose_master = "choose_master"
    ready = "ready"
    invalid_link = "invalid_link"
    revoked = "revoked"


class ClientMasterProjection(BaseModel):
    binding_id: uuid.UUID
    display_name: str
    public_contact: str | None = None


class ClientContextResponse(BaseModel):
    state: ClientEntryState
    message: str
    master: ClientMasterProjection | None = None
    masters: list[ClientMasterProjection] = Field(default_factory=list)


class ClientStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_token: str = Field(min_length=1, max_length=96)
    requested_public_name: str = Field(min_length=1, max_length=160)

    @field_validator("start_token")
    @classmethod
    def normalize_start_token(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("start_token must not be empty")
        return candidate

    @field_validator("requested_public_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("requested_public_name must not be empty")
        return candidate


class ClientPublicCatalogItem(BaseModel):
    public_name: str
    public_description: str | None
    kind: ServiceKindValue
    price_type: ServicePriceTypeValue
    price_amount: Decimal | None
    price_min_amount: Decimal | None
    price_max_amount: Decimal | None
    price_unit: str | None
    currency: str
    duration_minutes: int | None
    extra_minutes: int
    category: str | None
    sort_order: int


class ClientPublicCatalogResponse(BaseModel):
    master: ClientMasterProjection
    services: list[ClientPublicCatalogItem]


class ClientPublicSlotsResponse(BaseModel):
    master: ClientMasterProjection
    day: date
    timezone: str
    weekday_iso: int
    availability_known: bool
    is_working: bool
    step_minutes: int
    service: ClientPublicCatalogItem
    starts_at: list[datetime]
