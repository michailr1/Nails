from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AssistantStyle = Literal["business", "friendly", "casual", "playful", "custom"]


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
    def require_custom_details(self) -> "AssistantStyleUpdateRequest":
        if self.style == "custom" and self.details is None:
            raise ValueError("custom style requires details")
        return self


class MasterPreferencesResponse(BaseModel):
    preferred_name: str | None
    assistant_style: AssistantStyle | None
    assistant_style_details: str | None
    is_complete: bool
