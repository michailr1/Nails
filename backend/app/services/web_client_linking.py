from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.client_models import (
    BookingRequest,
    ClientTelegramIdentity,
    ClientTelegramIdentityStatus,
    MasterLinkToken,
    MasterPublicProfile,
)
from app.client_notification_models import ClientPersonalLinkToken
from app.config import get_settings
from app.models import Client, ClientProfileStatus
from app.schemas.client_linking import (
    ClientPhonePreselect,
    ClientReachabilityItem,
    ClientReachabilityListResponse,
    MasterPublicProfileResponse,
)
from app.services.client_linking import normalize_phone
from app.services.scheduling_common import SchedulingDomainError

_INVITATION_LEAD = (
    "Записаться ко мне можно в Telegram — там есть прайс и свободное время."
)


def client_invitation_url(start_token: str | None) -> str | None:
    username = get_settings().client_telegram_bot_username
    if not username or not start_token:
        return None
    return f"https://t.me/{username}?start={quote(start_token, safe='')}"


def invitation_copy(invitation_url: str | None) -> str:
    if invitation_url is None:
        return _INVITATION_LEAD
    return f"{_INVITATION_LEAD}\n\n{invitation_url}"


def public_profile_response(
    session: Session,
    identity: RequestIdentity,
) -> MasterPublicProfileResponse:
    profile = session.get(MasterPublicProfile, identity.user_id)
    if profile is None or not profile.display_name.strip():
        return MasterPublicProfileResponse(ready=False)
    return MasterPublicProfileResponse(
        ready=True,
        display_name=profile.display_name.strip(),
        public_contact=(
            profile.public_contact.strip() if profile.public_contact else None
        ),
    )


def save_public_profile(
    session: Session,
    identity: RequestIdentity,
    *,
    display_name: str,
    public_contact: str | None,
) -> MasterPublicProfileResponse:
    profile = session.get(MasterPublicProfile, identity.user_id)
    if profile is None:
        profile = MasterPublicProfile(
            owner_user_id=identity.user_id,
            display_name=display_name,
            public_contact=public_contact,
        )
        session.add(profile)
    else:
        profile.display_name = display_name
        profile.public_contact = public_contact
    session.commit()
    return public_profile_response(session, identity)


def _require_public_profile(
    session: Session,
    identity: RequestIdentity,
) -> MasterPublicProfile:
    profile = session.get(MasterPublicProfile, identity.user_id)
    if profile is None or not profile.display_name.strip():
        raise SchedulingDomainError(
            "master_public_profile_required",
            status_code=409,
        )
    return profile


def get_or_create_general_invitation(
    session: Session,
    identity: RequestIdentity,
) -> str:
    if not get_settings().client_telegram_bot_username:
        raise SchedulingDomainError(
            "client_bot_username_not_configured",
            status_code=503,
        )
    _require_public_profile(session, identity)
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtext(f"general-invite:{identity.user_id}")
            )
        )
    )
    token = session.scalar(
        select(MasterLinkToken.token)
        .where(
            MasterLinkToken.owner_user_id == identity.user_id,
            MasterLinkToken.revoked_at.is_(None),
        )
        .order_by(MasterLinkToken.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if token is None:
        token = secrets.token_urlsafe(32)
        session.add(
            MasterLinkToken(
                token=token,
                owner_user_id=identity.user_id,
            )
        )
        session.commit()
    invitation_url = client_invitation_url(token)
    if invitation_url is None:
        raise SchedulingDomainError(
            "client_bot_username_not_configured",
            status_code=503,
        )
    return invitation_url


def booking_request_phone_preselect(
    session: Session,
    identity: RequestIdentity,
    *,
    booking_request_id: uuid.UUID,
) -> ClientPhonePreselect:
    request = session.scalar(
        select(BookingRequest).where(
            BookingRequest.id == booking_request_id,
            BookingRequest.owner_user_id == identity.user_id,
        )
    )
    if request is None:
        raise SchedulingDomainError("booking_request_not_found", status_code=404)
    binding = session.scalar(
        select(ClientTelegramIdentity).where(
            ClientTelegramIdentity.id == request.binding_id,
            ClientTelegramIdentity.owner_user_id == identity.user_id,
        )
    )
    phone = normalize_phone(binding.requested_phone if binding is not None else None)
    if phone is None:
        return ClientPhonePreselect()

    clients = session.scalars(
        select(Client).where(
            Client.owner_user_id == identity.user_id,
            Client.profile_status == ClientProfileStatus.active,
            Client.phone.is_not(None),
        )
    ).all()
    matches = [client for client in clients if normalize_phone(client.phone) == phone]
    if len(matches) != 1:
        return ClientPhonePreselect()
    candidate = matches[0]
    occupied = session.scalar(
        select(ClientTelegramIdentity.id).where(
            ClientTelegramIdentity.owner_user_id == identity.user_id,
            ClientTelegramIdentity.client_id == candidate.id,
            ClientTelegramIdentity.status == ClientTelegramIdentityStatus.active,
            ClientTelegramIdentity.id != request.binding_id,
        )
    )
    if occupied is not None:
        return ClientPhonePreselect()
    return ClientPhonePreselect(
        client_id=candidate.id,
        reason="Клиентка указала номер, совпадающий с этой карточкой",
    )


def list_client_reachability(
    session: Session,
    identity: RequestIdentity,
    *,
    connected_only: bool,
) -> ClientReachabilityListResponse:
    clients = session.scalars(
        select(Client)
        .where(
            Client.owner_user_id == identity.user_id,
            Client.profile_status == ClientProfileStatus.active,
        )
        .order_by(Client.public_name, Client.id)
    ).all()
    identities = session.scalars(
        select(ClientTelegramIdentity).where(
            ClientTelegramIdentity.owner_user_id == identity.user_id,
            ClientTelegramIdentity.status == ClientTelegramIdentityStatus.active,
            ClientTelegramIdentity.client_id.is_not(None),
        )
    ).all()
    by_client = {row.client_id: row for row in identities if row.client_id is not None}
    items: list[ClientReachabilityItem] = []
    for client in clients:
        binding = by_client.get(client.id)
        state = "not_connected" if binding is None else binding.bot_reachability
        if connected_only and state in {"not_connected", "unreachable"}:
            continue
        items.append(ClientReachabilityItem(client_id=client.id, state=state))

    profile = public_profile_response(session, identity)
    token = session.scalar(
        select(MasterLinkToken.token)
        .where(
            MasterLinkToken.owner_user_id == identity.user_id,
            MasterLinkToken.revoked_at.is_(None),
        )
        .order_by(MasterLinkToken.created_at.desc())
        .limit(1)
    )
    invitation_url = client_invitation_url(token) if profile.ready else None
    return ClientReachabilityListResponse(
        items=items,
        invitation_text=invitation_copy(invitation_url),
        invitation_url=invitation_url,
        invitation_available=(
            profile.ready and bool(get_settings().client_telegram_bot_username)
        ),
        public_profile=profile,
    )


def revoke_open_personal_links(
    session: Session,
    identity: RequestIdentity,
    *,
    client_id: uuid.UUID,
) -> bool:
    client = session.scalar(
        select(Client.id).where(
            Client.id == client_id,
            Client.owner_user_id == identity.user_id,
            Client.profile_status == ClientProfileStatus.active,
        )
    )
    if client is None:
        raise SchedulingDomainError("client_not_found", status_code=404)
    rows = session.scalars(
        select(ClientPersonalLinkToken)
        .where(
            ClientPersonalLinkToken.owner_user_id == identity.user_id,
            ClientPersonalLinkToken.client_id == client_id,
            ClientPersonalLinkToken.revoked_at.is_(None),
            ClientPersonalLinkToken.consumed_at.is_(None),
            ClientPersonalLinkToken.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    ).all()
    if not rows:
        return False
    now = datetime.now(UTC)
    for row in rows:
        row.revoked_at = now
    session.commit()
    return True


def master_public_name(session: Session, identity: RequestIdentity) -> str:
    profile = session.get(MasterPublicProfile, identity.user_id)
    if profile is None or not profile.display_name.strip():
        return "мастер"
    return profile.display_name.strip()
