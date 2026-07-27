from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.client_models import ClientTelegramIdentity, MasterLinkToken, MasterPublicProfile
from app.models import User, UserRole


class ClientBindingError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PublicMaster:
    display_name: str
    public_contact: str | None


@dataclass(frozen=True, slots=True)
class ResolvedClientContext:
    owner_user_id: object
    telegram_user_id: int
    master: PublicMaster


def _available_master(session: Session, owner_user_id: object) -> User:
    owner = session.get(User, owner_user_id)
    if owner is None or owner.role != UserRole.master or not owner.is_active:
        raise ClientBindingError("master_unavailable")
    return owner


def _public_master(session: Session, owner_user_id: object) -> PublicMaster:
    profile = session.get(MasterPublicProfile, owner_user_id)
    if profile is None or not profile.display_name.strip():
        raise ClientBindingError("master_link_inactive")
    return PublicMaster(
        display_name=profile.display_name.strip(),
        public_contact=profile.public_contact.strip() if profile.public_contact else None,
    )


def resolve_start_token(
    session: Session,
    *,
    start_token: str,
    telegram_user_id: int,
) -> ResolvedClientContext:
    token = (start_token or "").strip()
    if not token or telegram_user_id <= 0:
        raise ClientBindingError("invalid_master_link")

    link = session.get(MasterLinkToken, token)
    if link is None or link.revoked_at is not None:
        raise ClientBindingError("invalid_master_link")

    owner = _available_master(session, link.owner_user_id)
    master = _public_master(session, owner.id)
    return ResolvedClientContext(
        owner_user_id=owner.id,
        telegram_user_id=telegram_user_id,
        master=master,
    )


def list_client_masters(session: Session, *, telegram_user_id: int) -> list[PublicMaster]:
    rows = session.execute(
        select(MasterPublicProfile)
        .join(
            ClientTelegramIdentity,
            ClientTelegramIdentity.owner_user_id == MasterPublicProfile.owner_user_id,
        )
        .join(User, User.id == ClientTelegramIdentity.owner_user_id)
        .where(
            ClientTelegramIdentity.telegram_user_id == telegram_user_id,
            ClientTelegramIdentity.status.in_(("pending", "active")),
            User.role == UserRole.master,
            User.is_active.is_(True),
        )
        .order_by(MasterPublicProfile.display_name, MasterPublicProfile.owner_user_id)
    ).scalars()
    return [
        PublicMaster(
            display_name=row.display_name.strip(),
            public_contact=row.public_contact.strip() if row.public_contact else None,
        )
        for row in rows
        if row.display_name.strip()
    ]


def create_master_link_token(
    session: Session,
    *,
    owner_user_id: object,
) -> MasterLinkToken:
    owner = _available_master(session, owner_user_id)
    _public_master(session, owner.id)

    for _ in range(5):
        token = secrets.token_urlsafe(32)
        if session.get(MasterLinkToken, token) is None:
            link = MasterLinkToken(token=token, owner_user_id=owner.id)
            session.add(link)
            session.flush()
            return link
    raise ClientBindingError("master_link_token_generation_failed")


def revoke_master_link_token(session: Session, *, token: str) -> None:
    link = session.get(MasterLinkToken, token)
    if link is not None and link.revoked_at is None:
        link.revoked_at = datetime.now(UTC)
        session.flush()
