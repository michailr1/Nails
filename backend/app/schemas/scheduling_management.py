from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.scheduling import ClientSummary, DayBookingSummary


class ClientCandidateListResponse(BaseModel):
    candidates: list[ClientSummary]


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
