from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.client_models import ClientTelegramIdentityStatus
from app.schemas.scheduling import ServiceKindValue, ServicePriceTypeValue


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
    services: list[ClientPublicCatalogItem]


class ClientPublicSlotsResponse(BaseModel):
    day: date
    timezone: str
    weekday_iso: int
    availability_known: bool
    is_working: bool
    step_minutes: int
    service: ClientPublicCatalogItem
    starts_at: list[datetime]


class ClientIdentitySummary(BaseModel):
    status: ClientTelegramIdentityStatus
    display_name: str | None
    phone_shared: bool
    linked: bool


class ClientIdentityLookupResponse(BaseModel):
    found: bool
    identity: ClientIdentitySummary | None = None


class ClientIdentityUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_public_name: str = Field(min_length=1, max_length=160)
    requested_phone: str | None = Field(default=None, max_length=32)
    contact_user_id: int | None = Field(default=None, gt=0)
    confirmed: bool

    @field_validator("requested_public_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("requested_public_name must not be empty")
        return candidate

    @field_validator("requested_phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = " ".join(value.split())
        return candidate or None

    @model_validator(mode="after")
    def validate_contact_and_confirmation(self) -> ClientIdentityUpsertRequest:
        if self.confirmed is not True:
            raise ValueError("confirmed must be true")
        if (self.requested_phone is None) != (self.contact_user_id is None):
            raise ValueError("phone and contact_user_id must be provided together")
        return self


class ClientIdentityUpsertResponse(BaseModel):
    identity: ClientIdentitySummary
    created: bool
    changed: bool
