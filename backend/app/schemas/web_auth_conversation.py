from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationalChallengeLookupResponse(BaseModel):
    status: str
    expires_at: datetime | None
    remaining_seconds: int = Field(ge=0)


class ConversationalChallengeDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_number: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$",
    )
    decision: Literal["approve", "deny"]


class ConversationalChallengeDecisionResponse(BaseModel):
    status: str
    expires_at: datetime | None
    remaining_seconds: int = Field(ge=0)
