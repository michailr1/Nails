from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity
from app.client_models import (
    BookingRequest,
    ClientContactForward,
    ClientTelegramIdentity,
)
from app.models import User, UserRole
from app.schemas.client_contour import (
    ClientContactForwardAckResponse,
    ClientContactForwardClaim,
    ClientContactForwardResponse,
)
from app.services.client_contour import require_client_binding
from app.services.scheduling_common import SchedulingDomainError
from app.timezones import owner_timezone

CLAIM_TTL = timedelta(minutes=5)


def enqueue_client_contact_forward(
    session: Session,
    identity: ClientTransportIdentity,
    *,
    binding_id: uuid.UUID,
    message_text: str,
) -> ClientContactForwardResponse:
    context = require_client_binding(
        session,
        identity,
        binding_id=binding_id,
    )
    if context.master.public_contact:
        raise SchedulingDomainError(
            code="client_public_contact_available",
            status_code=409,
        )

    binding = session.get(ClientTelegramIdentity, binding_id)
    if binding is None or binding.owner_user_id != context.owner_user_id:
        raise SchedulingDomainError(
            code="client_binding_not_found",
            status_code=404,
        )

    client_name = (binding.requested_public_name or "Клиентка").strip() or "Клиентка"
    row = ClientContactForward(
        owner_user_id=context.owner_user_id,
        binding_id=binding.id,
        kind="client_message",
        client_public_name=client_name,
        message_text=message_text,
    )
    session.add(row)
    session.commit()
    return ClientContactForwardResponse(
        accepted=True,
        message="Передам мастеру.",
    )


def enqueue_booking_request_master_forward(
    session: Session,
    request: BookingRequest,
) -> None:
    """Add a durable master notification to the caller's request transaction."""
    timezone = owner_timezone(session, request.owner_user_id)
    local_start = request.starts_at.astimezone(timezone)
    addons = list(request.addon_names or [])
    addon_text = ", ".join(addons) if addons else "без дополнений"
    client_name = (request.requested_public_name or "Клиентка").strip() or "Клиентка"
    lines = [
        f"Процедура: {request.service_name}",
        f"Дополнения: {addon_text}",
        f"Время: {local_start:%d.%m в %H:%M}",
    ]
    if request.note:
        lines.extend(("", f"Заметка клиентки: {request.note}"))
    lines.extend(("", "Откройте кабинет, чтобы проверить, изменить и подтвердить заявку."))
    message_text = "\n".join(lines)
    session.add(
        ClientContactForward(
            owner_user_id=request.owner_user_id,
            binding_id=request.binding_id,
            kind="booking_request_created",
            dedupe_key=f"booking-request:{request.id}",
            client_public_name=client_name,
            message_text=message_text,
        )
    )


def claim_client_contact_forward(session: Session) -> ClientContactForwardClaim:
    now = datetime.now(UTC)
    stale_before = now - CLAIM_TTL
    row = session.scalar(
        select(ClientContactForward)
        .join(User, User.id == ClientContactForward.owner_user_id)
        .where(
            ClientContactForward.sent_at.is_(None),
            User.is_active.is_(True),
            User.role == UserRole.master,
            (
                ClientContactForward.claimed_at.is_(None)
                | (ClientContactForward.claimed_at < stale_before)
            ),
        )
        .order_by(ClientContactForward.created_at, ClientContactForward.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if row is None:
        return ClientContactForwardClaim(claimed=False)

    master = session.get(User, row.owner_user_id)
    if master is None:
        return ClientContactForwardClaim(claimed=False)

    claim_id = uuid.uuid4()
    row.claim_id = claim_id
    row.claimed_at = now
    session.commit()
    return ClientContactForwardClaim(
        claimed=True,
        claim_id=claim_id,
        forward_id=row.id,
        master_telegram_user_id=master.telegram_user_id,
        kind=row.kind,
        client_public_name=row.client_public_name,
        message_text=row.message_text,
    )


def acknowledge_client_contact_forward(
    session: Session,
    *,
    claim_id: uuid.UUID,
    sent: bool,
) -> ClientContactForwardAckResponse:
    row = session.scalar(
        select(ClientContactForward)
        .where(ClientContactForward.claim_id == claim_id)
        .with_for_update()
    )
    if row is None:
        return ClientContactForwardAckResponse(changed=False, sent=sent)

    if sent:
        if row.sent_at is None:
            row.sent_at = datetime.now(UTC)
        changed = True
    else:
        row.claim_id = None
        row.claimed_at = None
        changed = True
    session.commit()
    return ClientContactForwardAckResponse(changed=changed, sent=sent)
