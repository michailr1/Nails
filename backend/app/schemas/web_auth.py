from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChallengeStartResponse(BaseModel):
    challenge_id: uuid.UUID
    confirmation_code: str
    expires_at: datetime
    csrf_token: str


class ChallengeStatusResponse(BaseModel):
    challenge_id: uuid.UUID
    status: str
    expires_at: datetime


class ChallengeConsumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: uuid.UUID


class ChallengeConsumeResponse(BaseModel):
    authenticated: bool
    status: str


class TelegramChallengeApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_code: str = Field(min_length=6, max_length=12)

    @field_validator("confirmation_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        candidate = "".join(value.split())
        if not candidate.isdigit():
            raise ValueError("confirmation_code must contain only digits")
        return candidate


class TelegramChallengeApproveResponse(BaseModel):
    approved: bool


class WebSessionStateResponse(BaseModel):
    authenticated: bool


class LogoutResponse(BaseModel):
    logged_out: bool
