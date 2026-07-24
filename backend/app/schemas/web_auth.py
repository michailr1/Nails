from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChallengeStartResponse(BaseModel):
    challenge_id: uuid.UUID
    verification_number: str
    expires_at: datetime


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

    challenge_id: uuid.UUID
    verification_number: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$",
    )


class TelegramChallengeApproveResponse(BaseModel):
    approved: bool


class WebSessionStateResponse(BaseModel):
    authenticated: bool
    role: str | None = None
    target_owner_user_id: uuid.UUID | None = None


class LogoutResponse(BaseModel):
    logged_out: bool
