from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BookingRequestStatusValue(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class BookingRequestResolutionValue(StrEnum):
    link_existing = "link_existing"
    create_new = "create_new"


def _normalize_addons(values: list[str]) -> list[str]:
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


def _normalize_quantities(values: dict[str, int]) -> dict[str, int]:
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


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("starts_at must include a timezone offset")
    return value


def _validate_composition(
    service_name: str,
    addon_names: list[str],
    addon_quantities: dict[str, int],
) -> None:
    addon_keys = {name.casefold() for name in addon_names}
    if service_name.casefold() in addon_keys:
        raise ValueError("base service cannot also be an addon")
    if set(addon_quantities) - addon_keys:
        raise ValueError("addon quantities require matching addon names")


class ClientBookingRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(min_length=1, max_length=160)
    addon_names: list[str] = Field(default_factory=list, max_length=20)
    addon_quantities: dict[str, int] = Field(default_factory=dict, max_length=20)
    starts_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("service_name", "idempotency_key")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("value must not be empty")
        return candidate

    @field_validator("addon_names")
    @classmethod
    def normalize_addons(cls, values: list[str]) -> list[str]:
        return _normalize_addons(values)

    @field_validator("addon_quantities")
    @classmethod
    def normalize_quantities(cls, values: dict[str, int]) -> dict[str, int]:
        return _normalize_quantities(values)

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @model_validator(mode="after")
    def validate_composition(self) -> ClientBookingRequestCreate:
        _validate_composition(
            self.service_name,
            self.addon_names,
            self.addon_quantities,
        )
        return self


class MasterBookingRequestApprove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: BookingRequestResolutionValue
    client_id: uuid.UUID | None = None
    service_name: str | None = Field(default=None, min_length=1, max_length=160)
    addon_names: list[str] | None = Field(default=None, max_length=20)
    addon_quantities: dict[str, int] | None = Field(default=None, max_length=20)
    starts_at: datetime | None = None
    price_override_amount: Decimal | None = Field(default=None, ge=0)
    duration_override_minutes: int | None = Field(default=None, ge=1, le=1440)

    @field_validator("service_name")
    @classmethod
    def normalize_service_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("service_name must not be empty")
        return candidate

    @field_validator("addon_names")
    @classmethod
    def normalize_addons(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _normalize_addons(values)

    @field_validator("addon_quantities")
    @classmethod
    def normalize_quantities(
        cls, values: dict[str, int] | None
    ) -> dict[str, int] | None:
        return None if values is None else _normalize_quantities(values)

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_timezone(value)

    @model_validator(mode="after")
    def validate_resolution(self) -> MasterBookingRequestApprove:
        if self.resolution == BookingRequestResolutionValue.link_existing:
            if self.client_id is None:
                raise ValueError("client_id is required when linking an existing client")
        elif self.client_id is not None:
            raise ValueError("client_id is not allowed when creating a new client")
        if self.service_name is not None and self.addon_names is not None:
            _validate_composition(
                self.service_name,
                self.addon_names,
                self.addon_quantities or {},
            )
        elif self.addon_quantities:
            if self.addon_names is None:
                raise ValueError("addon_names are required with addon_quantities")
            if set(self.addon_quantities) - {
                name.casefold() for name in self.addon_names
            }:
                raise ValueError("addon quantities require matching addon names")
        return self


class BookingRequestPublic(BaseModel):
    id: uuid.UUID
    status: BookingRequestStatusValue
    client_id: uuid.UUID | None = None
    requested_public_name: str | None = None
    service_name: str
    addon_names: list[str]
    addon_quantities: dict[str, int]
    starts_at: datetime
    booking_id: uuid.UUID | None = None
    created_at: datetime


class BookingRequestListResponse(BaseModel):
    requests: list[BookingRequestPublic]


class MasterBookingRequestPublic(BookingRequestPublic):
    note: str | None = None


class MasterBookingRequestListResponse(BaseModel):
    requests: list[MasterBookingRequestPublic]
