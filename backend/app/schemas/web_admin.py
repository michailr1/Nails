from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminMasterCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telegram_user_id: int = Field(gt=0)


class AdminMasterCard(BaseModel):
    id: uuid.UUID
    telegram_user_id: int
    is_active: bool
    onboarding_status: str
    created_at: datetime


class AdminMasterListResponse(BaseModel):
    masters: list[AdminMasterCard]


class AdminMasterCreateResponse(BaseModel):
    master: AdminMasterCard
    created: bool
    reactivated: bool = False


class AdminMasterDisableResponse(BaseModel):
    master: AdminMasterCard
    changed: bool


class AdminMasterSelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    master_user_id: uuid.UUID


class AdminMasterSelectResponse(BaseModel):
    master: AdminMasterCard
