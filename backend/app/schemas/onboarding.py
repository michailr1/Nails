from datetime import datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import OnboardingSection, OnboardingStatus


class ScheduleDayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(ge=0, le=6)
    is_working: bool = True
    start_time: time | None = None
    end_time: time | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> "ScheduleDayInput":
        if self.is_working:
            if self.start_time is None or self.end_time is None:
                raise ValueError("working day requires start_time and end_time")
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be later than start_time")
        elif self.start_time is not None or self.end_time is not None:
            raise ValueError("non-working day must not contain a time interval")
        return self


class SchedulePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: list[ScheduleDayInput] = Field(min_length=1, max_length=7)

    @field_validator("days")
    @classmethod
    def unique_weekdays(cls, value: list[ScheduleDayInput]) -> list[ScheduleDayInput]:
        weekdays = [item.weekday for item in value]
        if len(weekdays) != len(set(weekdays)):
            raise ValueError("weekday values must be unique")
        return sorted(value, key=lambda item: item.weekday)


class ServiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_name: str = Field(min_length=1, max_length=160)
    public_description: str | None = Field(default=None, max_length=2000)
    price_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    duration_minutes: int = Field(ge=5, le=1440)

    @field_validator("public_name")
    @classmethod
    def normalize_public_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("public_name must not be empty")
        return candidate


class ServicesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    services: list[ServiceInput] = Field(min_length=1, max_length=200)

    @field_validator("services")
    @classmethod
    def unique_service_names(cls, value: list[ServiceInput]) -> list[ServiceInput]:
        names = [item.public_name.casefold() for item in value]
        if len(names) != len(set(names)):
            raise ValueError("service public names must be unique")
        return value


class BufferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(min_length=1, max_length=160)
    before_minutes: int = Field(default=0, ge=0, le=240)
    after_minutes: int = Field(default=0, ge=0, le=240)

    @field_validator("service_name")
    @classmethod
    def normalize_service_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("service_name must not be empty")
        return candidate


class BuffersPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buffers: list[BufferInput] = Field(default_factory=list, max_length=200)

    @field_validator("buffers")
    @classmethod
    def unique_buffer_services(cls, value: list[BufferInput]) -> list[BufferInput]:
        names = [item.service_name.casefold() for item in value]
        if len(names) != len(set(names)):
            raise ValueError("buffer service names must be unique")
        return value


class BookingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_public_name: str = Field(min_length=1, max_length=160)
    client_phone: str | None = Field(default=None, max_length=32)
    service_name: str = Field(min_length=1, max_length=160)
    starts_at: datetime

    @field_validator("client_public_name", "service_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("name must not be empty")
        return candidate

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset")
        return value


class BookingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bookings: list[BookingInput] = Field(default_factory=list, max_length=500)


class DraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]


class DraftResponse(BaseModel):
    section: OnboardingSection
    draft_payload: dict[str, Any]
    confirmed_payload: dict[str, Any] | None
    effective_payload: dict[str, Any] | None
    revision: int
    confirmed_revision: int | None
    is_current_revision_confirmed: bool
    confirmed_at: datetime | None
    updated_at: datetime


class OnboardingStateResponse(BaseModel):
    status: OnboardingStatus
    current_step: OnboardingSection | None
    started_at: datetime | None
    completed_at: datetime | None
    sections: list[DraftResponse]
