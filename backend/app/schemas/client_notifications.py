from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClientNotificationClaim(BaseModel):
    claimed: bool
    claim_id: uuid.UUID | None = None
    notification_id: uuid.UUID | None = None
    telegram_user_id: int | None = None
    event_type: Literal["approved", "rejected", "cancelled"] | None = None
    timezone: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    attempts: int = 0


class ClientNotificationAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: uuid.UUID
    outcome: Literal["sent", "retry", "unreachable"]
    error_code: str | None = Field(default=None, max_length=64)


class ClientNotificationAckResponse(BaseModel):
    changed: bool
    status: Literal["pending", "sent", "failed"]
    attempts: int
    next_attempt_at: datetime | None = None


class ClientNotificationQueueHealth(BaseModel):
    pending_count: int
    claimed_count: int
    failed_count: int
    oldest_pending_age_seconds: int | None = None


class ClientNotificationSentItem(BaseModel):
    notification_id: uuid.UUID
    event_type: str
    status: str
    attempts: int
    created_at: datetime
    delivered_at: datetime | None
