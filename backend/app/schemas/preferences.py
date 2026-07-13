from __future__ import annotations

from datetime import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

type AssistantStyle = Literal["business", "friendly", "casual", "playful", "custom"]


class PreferredNameUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_name: str = Field(min_length=1, max_length=160)

    @field_validator("preferred_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("preferred_name must not be empty")
        return candidate


class AssistantStyleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: AssistantStyle
    details: str | None = Field(default=None, max_length=500)

    @field_validator("details")
    @classmethod
    def normalize_details(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = " ".join(value.split())
        return candidate or None

    @model_validator(mode="after")
    def require_custom_details(self) -> AssistantStyleUpdateRequest:
        if self.style == "custom" and self.details is None:
            raise ValueError("custom style requires details")
        return self


class DefaultWorkInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_interval(self) -> DefaultWorkInterval:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class DefaultWorkHoursUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervals: list[DefaultWorkInterval] = Field(default_factory=list, max_length=4)

    @field_validator("intervals")
    @classmethod
    def sort_and_reject_overlaps(
        cls,
        value: list[DefaultWorkInterval],
    ) -> list[DefaultWorkInterval]:
        ordered = sorted(value, key=lambda item: item.start_time)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.start_time < previous.end_time:
                raise ValueError("default work intervals must not overlap")
        return ordered


class MasterPreferencesResponse(BaseModel):
    preferred_name: str | None
    assistant_style: AssistantStyle | None
    assistant_style_details: str | None
    default_work_intervals: list[DefaultWorkInterval] | None
    is_complete: bool
