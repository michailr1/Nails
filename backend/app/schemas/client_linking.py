from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfirmedTelegramContactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_user_id: int = Field(gt=0)
    phone_number: str = Field(min_length=7, max_length=32)


class ConfirmedTelegramContactResponse(BaseModel):
    linked: bool
    result: Literal["linked", "no_match", "ambiguous", "unavailable"]


class ManualPhoneHintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_number: str = Field(min_length=7, max_length=32)


class ManualPhoneHintResponse(BaseModel):
    accepted: bool


class PersonalClientLinkResponse(BaseModel):
    token: str
    expires_at: datetime
    client_id: uuid.UUID


class GeneralClientInviteResponse(BaseModel):
    invitation_url: str


class PersonalClientInviteResponse(BaseModel):
    invitation_url: str
    expires_at: datetime
    client_id: uuid.UUID


class PersonalClientLinkRevokeResponse(BaseModel):
    changed: bool


class ClientLinkNoticeItem(BaseModel):
    link_record_id: uuid.UUID
    client_id: uuid.UUID
    client_public_name: str
    source: Literal["confirmed_contact", "personal_link", "master_approval"]
    created_at: datetime
    can_undo: bool


class ClientLinkNoticeListResponse(BaseModel):
    items: list[ClientLinkNoticeItem]


class ClientLinkUndoResponse(BaseModel):
    changed: bool


class ClientReachabilityItem(BaseModel):
    client_id: uuid.UUID
    state: Literal["reachable", "unknown", "unreachable", "not_connected"]


class ClientReachabilityListResponse(BaseModel):
    items: list[ClientReachabilityItem]
    invitation_text: str
    invitation_url: str | None = None
    invitation_available: bool = False


class ClientPhonePreselect(BaseModel):
    client_id: uuid.UUID | None = None
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def safe_reason(cls, value: str | None) -> str | None:
        return value
