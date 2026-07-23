from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.web_read import WebCalendarBooking


class WebBookingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_public_name: str = Field(min_length=1, max_length=160)
    service_name: str = Field(min_length=1, max_length=160)
    addon_names: list[str] = Field(default_factory=list, max_length=20)
    addon_quantities: dict[str, int] = Field(default_factory=dict, max_length=20)
    starts_at: datetime
    price_override_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    duration_override_minutes: int | None = Field(default=None, ge=1, le=1440)

    @field_validator("client_public_name", "service_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("value must not be empty")
        return candidate

    @field_validator("addon_names")
    @classmethod
    def normalize_addon_names(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            candidate = " ".join(value.split())
            if not candidate or len(candidate) > 160:
                raise ValueError("addon name is invalid")
            key = candidate.casefold()
            if key in seen:
                raise ValueError("addon names must be unique")
            seen.add(key)
            normalized.append(candidate)
        return normalized

    @field_validator("addon_quantities")
    @classmethod
    def normalize_addon_quantities(cls, values: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for raw_name, quantity in values.items():
            name = " ".join(raw_name.split())
            if not name or len(name) > 160:
                raise ValueError("addon quantity name is invalid")
            if quantity < 1 or quantity > 100:
                raise ValueError("addon quantity must be between 1 and 100")
            key = name.casefold()
            if key in normalized:
                raise ValueError("addon quantity names must be unique")
            normalized[key] = quantity
        return normalized

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_composition(self) -> WebBookingUpdateRequest:
        base = self.service_name.casefold()
        addon_keys = {name.casefold() for name in self.addon_names}
        if base in addon_keys:
            raise ValueError("base service cannot also be an addon")
        if set(self.addon_quantities) - addon_keys:
            raise ValueError("addon quantities require matching addon names")
        return self

    def quantity_for(self, addon_name: str) -> int:
        return self.addon_quantities.get(addon_name.casefold(), 1)


class WebBookingUpdateResponse(BaseModel):
    booking: WebCalendarBooking
    changed: bool
    changed_fields: list[str]
