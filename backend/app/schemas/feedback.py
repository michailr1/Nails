from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.feedback_models import FeedbackKind


class FeedbackMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=1000)


class FeedbackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FeedbackKind
    context: list[FeedbackMessage] = Field(min_length=1, max_length=4)


class FeedbackEventResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    actor_user_id: uuid.UUID
    kind: FeedbackKind
    safe_context: list[FeedbackMessage]
    created_at: datetime


class FeedbackCreateResponse(BaseModel):
    saved: bool
    event_id: uuid.UUID


class FeedbackListResponse(BaseModel):
    events: list[FeedbackEventResponse]


class FeedbackDeleteResponse(BaseModel):
    deleted: bool
