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


class MasterPublicProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=160)
    public_contact: str | None = Field(default=None, max_length=160)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        candidate = " ".join(value.split())
        if not candidate:
            raise ValueError("display_name must not be empty")
        return candidate

    @field_validator("public_contact")
    @classmethod
    def normalize_public_contact(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = " ".join(value.split())
        return candidate or None


class MasterPublicProfileResponse(BaseModel):
    ready: bool
    display_name: str | None = None
    public_contact: str | None = None


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
    public_profile: MasterPublicProfileResponse


class ClientPhonePreselect(BaseModel):
    client_id: uuid.UUID | None = None
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def safe_reason(cls, value: str | None) -> str | None:
        return value
