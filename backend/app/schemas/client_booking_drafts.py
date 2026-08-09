from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.client_contour import ClientMasterProjection
from app.schemas.scheduling import ServicePriceTypeValue


class ClientBookingDraftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(min_length=1, max_length=160)

    @field_validator("service_name")
    @classmethod
    def normalize_service_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("service_name must not be empty")
        return candidate


class ClientBookingDraftCompositionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    addon_names: list[str] = Field(default_factory=list, max_length=20)
    addon_quantities: dict[str, int] = Field(default_factory=dict, max_length=20)

    @field_validator("addon_names")
    @classmethod
    def normalize_addons(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            candidate = " ".join(value.split())
            if not candidate or len(candidate) > 160:
                raise ValueError("addon name is invalid")
            key = candidate.casefold()
            if key in seen:
                raise ValueError("addon names must be unique")
            seen.add(key)
            result.append(candidate)
        return result

    @field_validator("addon_quantities")
    @classmethod
    def normalize_quantities(cls, values: dict[str, int]) -> dict[str, int]:
        result: dict[str, int] = {}
        for raw_name, quantity in values.items():
            name = " ".join(raw_name.split())
            if not name or len(name) > 160 or quantity < 1 or quantity > 100:
                raise ValueError("addon quantity is invalid")
            key = name.casefold()
            if key in result:
                raise ValueError("addon quantity names must be unique")
            result[key] = quantity
        return result

    @model_validator(mode="after")
    def quantities_require_addons(self) -> ClientBookingDraftCompositionUpdate:
        addon_keys = {name.casefold() for name in self.addon_names}
        if set(self.addon_quantities) - addon_keys:
            raise ValueError("addon quantities require matching addon names")
        return self


class ClientBookingDraftNoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=300)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None


class ClientBookingDraftSlotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset")
        return value


class ClientBookingAddonOption(BaseModel):
    public_name: str
    price_type: ServicePriceTypeValue
    price_amount: Decimal | None
    price_min_amount: Decimal | None
    price_max_amount: Decimal | None
    price_unit: str | None
    currency: str
    extra_minutes: int
    included_in_base: bool
    quantity_supported: bool
    time_per_unit: bool


class ClientBookingDraftSummary(BaseModel):
    draft_id: uuid.UUID
    master: ClientMasterProjection
    service_name: str
    addon_names: list[str]
    addon_quantities: dict[str, int]
    note: str | None = None
    starts_at: datetime | None
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    price_type: ServicePriceTypeValue
    price_amount: Decimal | None
    price_min_amount: Decimal | None
    price_max_amount: Decimal | None
    price_unit: str | None
    currency: str
    addons: list[ClientBookingAddonOption]
    expires_at: datetime


class ClientBookingDraftSlotsResponse(BaseModel):
    draft: ClientBookingDraftSummary
    day: date
    timezone: str
    availability_known: bool
    is_working: bool
    step_minutes: int
    starts_at: list[datetime]


class ClientBookingDraftSubmitResponse(BaseModel):
    request_id: uuid.UUID
    status: str
    service_name: str
    addon_names: list[str]
    addon_quantities: dict[str, int]
    starts_at: datetime
