from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.client_models import BookingRequest, ClientTelegramIdentity
from app.client_notification_models import ClientNotificationOutbox
from app.schemas.client_notifications import (
    ClientNotificationAckResponse,
    ClientNotificationClaim,
)
from app.timezones import owner_timezone_name

CLAIM_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5
_BASE_RETRY = timedelta(seconds=30)
_SAFE_EVENT_TYPES = {"approved", "rejected", "cancelled"}
_SAFE_PAYLOAD_KEYS = {"service_name", "starts_at", "booking_id"}


def _safe_payload(request: BookingRequest) -> dict[str, object]:
    payload: dict[str, object] = {
        "service_name": request.service_name,
        "starts_at": request.starts_at.isoformat(),
    }
    if request.booking_id is not None:
        payload["booking_id"] = str(request.booking_id)
    return payload


def enqueue_booking_request_notification(
    session: Session,
    request: BookingRequest,
    *,
    event_type: str,
) -> ClientNotificationOutbox:
    if event_type not in _SAFE_EVENT_TYPES:
        raise ValueError("unsupported client notification event")
    idempotency_key = f"booking-request:{request.id}:{event_type}"
    existing = session.scalar(
        select(ClientNotificationOutbox).where(
            ClientNotificationOutbox.owner_user_id == request.owner_user_id,
            ClientNotificationOutbox.binding_id == request.binding_id,
            ClientNotificationOutbox.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    row = ClientNotificationOutbox(
        owner_user_id=request.owner_user_id,
        binding_id=request.binding_id,
        booking_request_id=request.id,
        event_type=event_type,
        payload=_safe_payload(request),
        idempotency_key=idempotency_key,
    )
    session.add(row)
    session.flush()
    return row


def claim_client_notification(session: Session) -> ClientNotificationClaim:
    now = datetime.now(UTC)
    stale_before = now - CLAIM_TTL
    row = session.scalar(
        select(ClientNotificationOutbox)
        .where(
            ClientNotificationOutbox.attempts < MAX_ATTEMPTS,
            ClientNotificationOutbox.next_attempt_at <= now,
            (
                (ClientNotificationOutbox.status == "pending")
                | (
                    (ClientNotificationOutbox.status == "claimed")
                    & (ClientNotificationOutbox.claimed_at < stale_before)
                )
            ),
        )
        .order_by(
            ClientNotificationOutbox.next_attempt_at,
            ClientNotificationOutbox.created_at,
            ClientNotificationOutbox.id,
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if row is None:
        return ClientNotificationClaim(claimed=False)

    binding = session.get(ClientTelegramIdentity, row.binding_id)
    if binding is None:
        row.status = "failed"
        row.last_error_code = "binding_missing"
        session.commit()
        return ClientNotificationClaim(claimed=False)

    claim_id = uuid.uuid4()
    row.status = "claimed"
    row.claim_id = claim_id
    row.claimed_at = now
    row.attempts += 1
    timezone = owner_timezone_name(session, row.owner_user_id)
    session.commit()
    return ClientNotificationClaim(
        claimed=True,
        claim_id=claim_id,
        notification_id=row.id,
        telegram_user_id=binding.telegram_user_id,
        event_type=row.event_type,
        timezone=timezone,
        payload=dict(row.payload),
        attempts=row.attempts,
    )


def acknowledge_client_notification(
    session: Session,
    *,
    claim_id: uuid.UUID,
    outcome: str,
    error_code: str | None,
) -> ClientNotificationAckResponse:
    row = session.scalar(
        select(ClientNotificationOutbox)
        .where(
            ClientNotificationOutbox.claim_id == claim_id,
            ClientNotificationOutbox.status == "claimed",
        )
        .with_for_update()
    )
    if row is None:
        return ClientNotificationAckResponse(
            changed=False,
            status="failed",
            attempts=0,
        )

    now = datetime.now(UTC)
    binding = session.get(ClientTelegramIdentity, row.binding_id)
    if outcome == "sent":
        row.status = "sent"
        row.delivered_at = now
        row.last_error_code = None
        if binding is not None:
            binding.bot_reachability = "reachable"
            binding.last_delivery_at = now
        result_status = "sent"
        next_attempt_at = None
    elif outcome == "unreachable":
        row.status = "failed"
        row.last_error_code = error_code or "unreachable"
        if binding is not None:
            binding.bot_reachability = "unreachable"
            binding.last_delivery_at = now
        result_status = "failed"
        next_attempt_at = None
    else:
        row.last_error_code = error_code or "delivery_failed"
        if row.attempts >= MAX_ATTEMPTS:
            row.status = "failed"
            result_status = "failed"
            next_attempt_at = None
        else:
            delay = _BASE_RETRY * (2 ** max(row.attempts - 1, 0))
            row.status = "pending"
            row.next_attempt_at = now + delay
            result_status = "pending"
            next_attempt_at = row.next_attempt_at

    row.claim_id = None
    row.claimed_at = None
    session.commit()
    return ClientNotificationAckResponse(
        changed=True,
        status=result_status,
        attempts=row.attempts,
        next_attempt_at=next_attempt_at,
    )


def assert_safe_outbox_payload(payload: dict[str, object]) -> bool:
    return set(payload).issubset(_SAFE_PAYLOAD_KEYS)
