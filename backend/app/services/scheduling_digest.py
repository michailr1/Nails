from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import (
    AuditEvent,
    Booking,
    BookingStatus,
    Client,
    Service,
    User,
    UserRole,
)
from app.schemas.scheduling_digest import (
    FinalizationDigestAckRequest,
    FinalizationDigestAckResponse,
    FinalizationDigestBooking,
    FinalizationDigestClaimRequest,
    FinalizationDigestClaimResponse,
    FinalizationDigestOwnersResponse,
)
from app.services.scheduling_common import app_timezone, lock_owner_schedule


def list_digest_owners(session: Session) -> FinalizationDigestOwnersResponse:
    user_ids = session.scalars(
        select(User.telegram_user_id)
        .where(
            User.is_active.is_(True),
            User.role.in_((UserRole.master, UserRole.admin)),
        )
        .order_by(User.telegram_user_id)
    ).all()
    return FinalizationDigestOwnersResponse(telegram_user_ids=list(user_ids))


def _addon_names(snapshot: Any) -> list[str]:
    if not isinstance(snapshot, list):
        return []
    names: list[str] = []
    for item in snapshot:
        if not isinstance(item, dict) or item.get("kind") != "addon":
            continue
        public_name = item.get("public_name")
        if isinstance(public_name, str) and public_name.strip():
            names.append(public_name.strip())
    return names


def _price_amount(booking: Booking) -> Decimal | None:
    if booking.catalog_price_type_snapshot == "range":
        return booking.catalog_price_min_snapshot
    if booking.catalog_price_type_snapshot == "on_request":
        return None
    return booking.price_amount


def _digest_booking(
    booking: Booking,
    client: Client,
    service: Service,
) -> FinalizationDigestBooking:
    timezone = app_timezone()
    return FinalizationDigestBooking(
        client_public_name=client.public_name,
        service_name=service.public_name,
        addon_names=_addon_names(booking.catalog_items_snapshot),
        starts_at=booking.starts_at.astimezone(timezone),
        ends_at=booking.ends_at.astimezone(timezone),
        price_type=booking.catalog_price_type_snapshot,
        price_amount=_price_amount(booking),
        price_min_amount=booking.catalog_price_min_snapshot,
        price_max_amount=booking.catalog_price_max_snapshot,
        price_unit=booking.catalog_price_unit_snapshot,
        currency=booking.currency,
    )


def claim_finalization_digest(
    session: Session,
    identity: RequestIdentity,
    body: FinalizationDigestClaimRequest,
) -> FinalizationDigestClaimResponse:
    lock_owner_schedule(session, identity.user_id)
    existing = session.scalar(
        select(Booking.id)
        .where(
            Booking.owner_user_id == identity.user_id,
            text("finalization_digest_local_day = :local_day"),
        )
        .params(local_day=body.local_day)
        .limit(1)
    )
    if existing is not None:
        return FinalizationDigestClaimResponse(
            claimed=False,
            claim_id=None,
            local_day=body.local_day,
            bookings=[],
        )

    rows = session.execute(
        select(Booking, Client, Service)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.owner_user_id == identity.user_id,
            Booking.status == BookingStatus.scheduled,
            Booking.ends_at <= body.now.astimezone(UTC),
            text("finalization_digest_claim_id IS NULL"),
            text("finalization_digest_sent_at IS NULL"),
        )
        .order_by(Booking.starts_at, Booking.id)
        .with_for_update(skip_locked=True)
    ).all()
    if not rows:
        return FinalizationDigestClaimResponse(
            claimed=False,
            claim_id=None,
            local_day=body.local_day,
            bookings=[],
        )

    claim_id = uuid.uuid4()
    claimed_at = datetime.now(UTC)
    for booking, _, _ in rows:
        session.execute(
            text(
                """
                UPDATE bookings
                SET finalization_digest_claim_id = :claim_id,
                    finalization_digest_claimed_at = :claimed_at,
                    finalization_digest_local_day = :local_day
                WHERE owner_user_id = :owner_user_id
                  AND id = :booking_id
                  AND finalization_digest_claim_id IS NULL
                  AND finalization_digest_sent_at IS NULL
                """
            ),
            {
                "claim_id": claim_id,
                "claimed_at": claimed_at,
                "local_day": body.local_day,
                "owner_user_id": identity.user_id,
                "booking_id": booking.id,
            },
        )
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="booking.finalization_digest_claimed",
            object_type="booking_digest",
            object_id=None,
            request_id=identity.request_id,
            safe_changes={
                "local_day": body.local_day.isoformat(),
                "bookings_count": len(rows),
            },
        )
    )
    session.commit()
    return FinalizationDigestClaimResponse(
        claimed=True,
        claim_id=claim_id,
        local_day=body.local_day,
        bookings=[
            _digest_booking(booking, client, service)
            for booking, client, service in rows
        ],
    )


def acknowledge_finalization_digest(
    session: Session,
    identity: RequestIdentity,
    body: FinalizationDigestAckRequest,
) -> FinalizationDigestAckResponse:
    lock_owner_schedule(session, identity.user_id)
    rows = session.execute(
        select(Booking)
        .where(
            Booking.owner_user_id == identity.user_id,
            text("finalization_digest_claim_id = :claim_id"),
        )
        .params(claim_id=body.claim_id)
        .with_for_update()
    ).scalars().all()
    if not rows:
        return FinalizationDigestAckResponse(
            changed=False,
            sent=body.sent,
            bookings_count=0,
        )

    if body.sent:
        result = session.execute(
            text(
                """
                UPDATE bookings
                SET finalization_digest_sent_at = COALESCE(
                        finalization_digest_sent_at,
                        :sent_at
                    )
                WHERE owner_user_id = :owner_user_id
                  AND finalization_digest_claim_id = :claim_id
                  AND finalization_digest_sent_at IS NULL
                """
            ),
            {
                "sent_at": datetime.now(UTC),
                "owner_user_id": identity.user_id,
                "claim_id": body.claim_id,
            },
        )
    else:
        result = session.execute(
            text(
                """
                UPDATE bookings
                SET finalization_digest_claim_id = NULL,
                    finalization_digest_claimed_at = NULL,
                    finalization_digest_local_day = NULL
                WHERE owner_user_id = :owner_user_id
                  AND finalization_digest_claim_id = :claim_id
                  AND finalization_digest_sent_at IS NULL
                """
            ),
            {
                "owner_user_id": identity.user_id,
                "claim_id": body.claim_id,
            },
        )

    changed = bool(result.rowcount)
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action=(
                "booking.finalization_digest_sent"
                if body.sent
                else "booking.finalization_digest_released"
            ),
            object_type="booking_digest",
            object_id=None,
            request_id=identity.request_id,
            safe_changes={
                "sent": body.sent,
                "bookings_count": len(rows),
                "changed": changed,
            },
        )
    )
    session.commit()
    return FinalizationDigestAckResponse(
        changed=changed,
        sent=body.sent,
        bookings_count=len(rows),
    )
