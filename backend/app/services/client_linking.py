from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity, RequestIdentity
from app.client_models import ClientTelegramIdentity, ClientTelegramIdentityStatus
from app.client_notification_models import ClientLinkRecord, ClientPersonalLinkToken
from app.models import AuditEvent, Client, ClientProfileStatus
from app.schemas.client_linking import (
    ClientLinkNoticeItem,
    ClientLinkUndoResponse,
    ConfirmedTelegramContactResponse,
    ManualPhoneHintResponse,
    PersonalClientLinkResponse,
)
from app.services.client_contour import require_client_binding
from app.services.scheduling_common import SchedulingDomainError

PERSONAL_LINK_TTL = timedelta(days=7)


def normalize_phone(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    if len(digits) < 10 or len(digits) > 15:
        return None
    return digits


def _lock_owner_phone(session: Session, owner_user_id: uuid.UUID, phone: str) -> None:
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 11))"),
        {"key": f"client-phone:{owner_user_id}:{phone}"},
    )


def _active_phone_matches(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    normalized_phone: str,
) -> list[Client]:
    clients = session.scalars(
        select(Client)
        .where(
            Client.owner_user_id == owner_user_id,
            Client.profile_status == ClientProfileStatus.active,
            Client.phone.is_not(None),
        )
        .with_for_update()
    ).all()
    return [
        client
        for client in clients
        if normalize_phone(client.phone) == normalized_phone
    ]


def _bound_elsewhere(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    client_id: uuid.UUID,
    binding_id: uuid.UUID,
) -> bool:
    return (
        session.scalar(
            select(ClientTelegramIdentity.id).where(
                ClientTelegramIdentity.owner_user_id == owner_user_id,
                ClientTelegramIdentity.client_id == client_id,
                ClientTelegramIdentity.status == ClientTelegramIdentityStatus.active,
                ClientTelegramIdentity.id != binding_id,
            )
        )
        is not None
    )


def _record_link(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    binding: ClientTelegramIdentity,
    client: Client,
    source: str,
    request_id: str,
) -> ClientLinkRecord:
    binding.client_id = client.id
    binding.status = ClientTelegramIdentityStatus.active
    record = ClientLinkRecord(
        owner_user_id=owner_user_id,
        binding_id=binding.id,
        client_id=client.id,
        source=source,
    )
    session.add(record)
    session.add(
        AuditEvent(
            owner_user_id=owner_user_id,
            actor_user_id=None,
            action="client_identity.linked",
            object_type="client_telegram_identity",
            object_id=binding.id,
            request_id=request_id,
            safe_changes={
                "source": source,
                "client_id": str(client.id),
                "undo_available": source in {"confirmed_contact", "personal_link"},
            },
        )
    )
    session.flush()
    return record


def confirm_telegram_contact(
    session: Session,
    identity: ClientTransportIdentity,
    *,
    binding_id: uuid.UUID,
    contact_user_id: int,
    phone_number: str,
) -> ConfirmedTelegramContactResponse:
    if contact_user_id != identity.telegram_user_id:
        raise SchedulingDomainError("telegram_contact_identity_mismatch", status_code=403)
    phone = normalize_phone(phone_number)
    if phone is None:
        raise SchedulingDomainError("invalid_phone", status_code=422)
    context = require_client_binding(session, identity, binding_id=binding_id)
    binding = session.scalar(
        select(ClientTelegramIdentity)
        .where(
            ClientTelegramIdentity.id == binding_id,
            ClientTelegramIdentity.owner_user_id == context.owner_user_id,
            ClientTelegramIdentity.telegram_user_id == identity.telegram_user_id,
        )
        .with_for_update()
    )
    if binding is None:
        raise SchedulingDomainError("client_binding_not_found", status_code=404)
    if binding.status == ClientTelegramIdentityStatus.revoked:
        raise SchedulingDomainError("client_identity_revoked", status_code=403)
    if binding.status == ClientTelegramIdentityStatus.active:
        return ConfirmedTelegramContactResponse(linked=True, result="linked")

    _lock_owner_phone(session, context.owner_user_id, phone)
    matches = _active_phone_matches(
        session,
        owner_user_id=context.owner_user_id,
        normalized_phone=phone,
    )
    if not matches:
        return ConfirmedTelegramContactResponse(linked=False, result="no_match")
    if len(matches) != 1:
        return ConfirmedTelegramContactResponse(linked=False, result="ambiguous")
    client = matches[0]
    if _bound_elsewhere(
        session,
        owner_user_id=context.owner_user_id,
        client_id=client.id,
        binding_id=binding.id,
    ):
        return ConfirmedTelegramContactResponse(linked=False, result="unavailable")

    _record_link(
        session,
        owner_user_id=context.owner_user_id,
        binding=binding,
        client=client,
        source="confirmed_contact",
        request_id=identity.request_id,
    )
    session.commit()
    return ConfirmedTelegramContactResponse(linked=True, result="linked")


def set_manual_phone_hint(
    session: Session,
    identity: ClientTransportIdentity,
    *,
    binding_id: uuid.UUID,
    phone_number: str,
) -> ManualPhoneHintResponse:
    phone = normalize_phone(phone_number)
    if phone is None:
        raise SchedulingDomainError("invalid_phone", status_code=422)
    context = require_client_binding(session, identity, binding_id=binding_id)
    binding = session.scalar(
        select(ClientTelegramIdentity)
        .where(
            ClientTelegramIdentity.id == binding_id,
            ClientTelegramIdentity.owner_user_id == context.owner_user_id,
            ClientTelegramIdentity.telegram_user_id == identity.telegram_user_id,
        )
        .with_for_update()
    )
    if binding is None:
        raise SchedulingDomainError("client_binding_not_found", status_code=404)
    if binding.status == ClientTelegramIdentityStatus.revoked:
        raise SchedulingDomainError("client_identity_revoked", status_code=403)
    # This value is deliberately only a hint. It never calls _record_link().
    binding.requested_phone = phone
    session.add(
        AuditEvent(
            owner_user_id=context.owner_user_id,
            actor_user_id=None,
            action="client_identity.phone_hint_updated",
            object_type="client_telegram_identity",
            object_id=binding.id,
            request_id=identity.request_id,
            safe_changes={"source": "manual", "has_phone_hint": True},
        )
    )
    session.commit()
    return ManualPhoneHintResponse(accepted=True)


def create_personal_client_link(
    session: Session,
    identity: RequestIdentity,
    *,
    client_id: uuid.UUID,
) -> PersonalClientLinkResponse:
    client = session.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.owner_user_id == identity.user_id,
            Client.profile_status == ClientProfileStatus.active,
        )
    )
    if client is None:
        raise SchedulingDomainError("client_not_found", status_code=404)
    now = datetime.now(UTC)
    for _ in range(5):
        token = "c_" + secrets.token_urlsafe(30)
        if session.get(ClientPersonalLinkToken, token) is None:
            row = ClientPersonalLinkToken(
                token=token,
                owner_user_id=identity.user_id,
                client_id=client.id,
                expires_at=now + PERSONAL_LINK_TTL,
            )
            session.add(row)
            session.commit()
            return PersonalClientLinkResponse(
                token=row.token,
                expires_at=row.expires_at,
                client_id=client.id,
            )
    raise SchedulingDomainError("client_personal_link_generation_failed", status_code=500)


def revoke_personal_client_link(
    session: Session,
    identity: RequestIdentity,
    *,
    token: str,
) -> bool:
    row = session.scalar(
        select(ClientPersonalLinkToken)
        .where(
            ClientPersonalLinkToken.token == token,
            ClientPersonalLinkToken.owner_user_id == identity.user_id,
        )
        .with_for_update()
    )
    if row is None:
        raise SchedulingDomainError("client_personal_link_not_found", status_code=404)
    if row.revoked_at is None and row.consumed_at is None:
        row.revoked_at = datetime.now(UTC)
        session.commit()
        return True
    return False


def consume_personal_client_link(
    session: Session,
    identity: ClientTransportIdentity,
    *,
    token: str,
    requested_public_name: str,
) -> tuple[uuid.UUID, ClientTelegramIdentity]:
    now = datetime.now(UTC)
    row = session.scalar(
        select(ClientPersonalLinkToken)
        .where(ClientPersonalLinkToken.token == token)
        .with_for_update()
    )
    if (
        row is None
        or row.revoked_at is not None
        or row.consumed_at is not None
        or row.expires_at <= now
    ):
        raise SchedulingDomainError("invalid_client_personal_link", status_code=409)
    client = session.scalar(
        select(Client).where(
            Client.id == row.client_id,
            Client.owner_user_id == row.owner_user_id,
            Client.profile_status == ClientProfileStatus.active,
        )
    )
    if client is None:
        raise SchedulingDomainError("invalid_client_personal_link", status_code=409)

    binding = session.scalar(
        select(ClientTelegramIdentity)
        .where(
            ClientTelegramIdentity.owner_user_id == row.owner_user_id,
            ClientTelegramIdentity.telegram_user_id == identity.telegram_user_id,
        )
        .with_for_update()
    )
    if binding is None:
        binding = ClientTelegramIdentity(
            owner_user_id=row.owner_user_id,
            telegram_user_id=identity.telegram_user_id,
            status=ClientTelegramIdentityStatus.pending,
            requested_public_name=requested_public_name,
        )
        session.add(binding)
        session.flush()
    if binding.status == ClientTelegramIdentityStatus.revoked:
        raise SchedulingDomainError("client_identity_revoked", status_code=403)
    if binding.status == ClientTelegramIdentityStatus.active and binding.client_id != client.id:
        raise SchedulingDomainError("client_identity_already_linked", status_code=409)
    if _bound_elsewhere(
        session,
        owner_user_id=row.owner_user_id,
        client_id=client.id,
        binding_id=binding.id,
    ):
        raise SchedulingDomainError("client_already_linked", status_code=409)

    binding.requested_public_name = requested_public_name
    if binding.status != ClientTelegramIdentityStatus.active:
        _record_link(
            session,
            owner_user_id=row.owner_user_id,
            binding=binding,
            client=client,
            source="personal_link",
            request_id=identity.request_id,
        )
    row.consumed_at = now
    row.consumed_binding_id = binding.id
    session.commit()
    return row.owner_user_id, binding


def list_link_notices(
    session: Session,
    identity: RequestIdentity,
    *,
    limit: int = 20,
) -> list[ClientLinkNoticeItem]:
    rows = session.execute(
        select(ClientLinkRecord, Client)
        .join(Client, Client.id == ClientLinkRecord.client_id)
        .where(ClientLinkRecord.owner_user_id == identity.user_id)
        .order_by(ClientLinkRecord.created_at.desc())
        .limit(limit)
    ).all()
    return [
        ClientLinkNoticeItem(
            link_record_id=record.id,
            client_id=client.id,
            client_public_name=client.public_name,
            source=record.source,
            created_at=record.created_at,
            can_undo=(
                record.undone_at is None
                and record.source in {"confirmed_contact", "personal_link"}
            ),
        )
        for record, client in rows
    ]


def undo_client_link(
    session: Session,
    identity: RequestIdentity,
    *,
    link_record_id: uuid.UUID,
) -> ClientLinkUndoResponse:
    record = session.scalar(
        select(ClientLinkRecord)
        .where(
            ClientLinkRecord.id == link_record_id,
            ClientLinkRecord.owner_user_id == identity.user_id,
        )
        .with_for_update()
    )
    if record is None:
        raise SchedulingDomainError("client_link_record_not_found", status_code=404)
    if record.undone_at is not None:
        return ClientLinkUndoResponse(changed=False)
    if record.source not in {"confirmed_contact", "personal_link"}:
        raise SchedulingDomainError("client_link_not_undoable", status_code=409)
    binding = session.scalar(
        select(ClientTelegramIdentity)
        .where(
            ClientTelegramIdentity.id == record.binding_id,
            ClientTelegramIdentity.owner_user_id == identity.user_id,
        )
        .with_for_update()
    )
    if binding is None:
        raise SchedulingDomainError("client_binding_not_found", status_code=404)
    if (
        binding.status != ClientTelegramIdentityStatus.active
        or binding.client_id != record.client_id
    ):
        record.undone_at = datetime.now(UTC)
        session.commit()
        return ClientLinkUndoResponse(changed=False)

    binding.client_id = None
    binding.status = ClientTelegramIdentityStatus.pending
    record.undone_at = datetime.now(UTC)
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="client_identity.link_undone",
            object_type="client_telegram_identity",
            object_id=binding.id,
            request_id=identity.request_id,
            safe_changes={"source": record.source},
        )
    )
    session.commit()
    return ClientLinkUndoResponse(changed=True)
