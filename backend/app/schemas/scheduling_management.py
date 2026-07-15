from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.scheduling import DayBookingSummary


class ClientCardSummary(BaseModel):
    id: uuid.UUID
    public_name: str
    phone: str | None
    private_alias: str | None
    contact_channel: str | None
    birthday: date | None
    notes: str | None
    nail_skin_notes: str | None
    sensitivity_notes: str | None
    style_preferences: str | None
    communication_preferences: str | None


class ClientLookupResponse(BaseModel):
    found: bool
    client: ClientCardSummary | None = None


class ClientCandidateListResponse(BaseModel):
    candidates: list[ClientCardSummary]


class ClientCardDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    private_alias: str | None = Field(default=None, max_length=160)
    contact_channel: str | None = Field(default=None, max_length=80)
    birthday: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    nail_skin_notes: str | None = Field(default=None, max_length=4000)
    sensitivity_notes: str | None = Field(default=None, max_length=4000)
    style_preferences: str | None = Field(default=None, max_length=4000)
    communication_preferences: str | None = Field(default=None, max_length=2000)

    @field_validator("public_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("public_name must not be empty")
        return candidate

    @field_validator("phone", "private_alias", "contact_channel")
    @classmethod
    def normalize_short_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = " ".join(value.split())
        return candidate or None

    @field_validator(
        "notes",
        "nail_skin_notes",
        "sensitivity_notes",
        "style_preferences",
        "communication_preferences",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None


class ClientCreateRequest(ClientCardDefinition):
    pass


class ClientCreateResponse(BaseModel):
    client: ClientCardSummary
    created: bool
    contact_added: bool = False


class ClientReplaceRequest(ClientCardDefinition):
    current_public_name: str = Field(min_length=1, max_length=160)

    @field_validator("current_public_name")
    @classmethod
    def normalize_current_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("current_public_name must not be empty")
        return candidate


class ClientReplaceResponse(BaseModel):
    client: ClientCardSummary
    changed: bool
    changed_fields: list[str]


class BookingSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_public_name: str = Field(min_length=1, max_length=160)
    service_name: str = Field(min_length=1, max_length=160)
    starts_at: datetime

    @field_validator("client_public_name", "service_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("value must not be empty")
        return candidate

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset")
        return value


class BookingRescheduleRequest(BookingSelector):
    new_starts_at: datetime

    @field_validator("new_starts_at")
    @classmethod
    def require_new_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("new_starts_at must include a timezone offset")
        return value


class BookingCancelRequest(BookingSelector):
    pass


class BookingMutationResponse(BaseModel):
    booking: DayBookingSummary
    changed: bool
