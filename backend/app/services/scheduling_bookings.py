from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, Booking, BookingStatus, Client, Service
from app.schemas.scheduling import BookingCreateRequest, BookingCreateResponse
from app.services.normalization import normalize_public_name
from app.services.scheduling_common import (
    SchedulingDomainError,
    app_timezone,
    calculate_reservation,
    ensure_reservation_available,
    lock_owner_schedule,
)
from app.services.scheduling_lookup import get_active_client, get_active_service
from app.services.scheduling_presenters import booking_summary


def _find_idempotent_booking(
    session: Session,
    identity: RequestIdentity,
    body: BookingCreateRequest,
) -> tuple[Booking, Client, Service] | None:
    result = session.execute(
        select(Booking, Client, Service)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.owner_user_id == identity.user_id,
            Booking.idempotency_key == body.idempotency_key,
        )
        .with_for_update()
    ).first()
    if result is None:
        return None

    booking, client, service = result
    if (
        client.normalized_public_name != normalize_public_name(body.client_public_name)
        or service.normalized_public_name != normalize_public_name(body.service_name)
        or booking.starts_at.astimezone(UTC) != body.starts_at.astimezone(UTC)
    ):
        raise SchedulingDomainError("idempotency_conflict")
    return booking, client, service


def create_booking(
    session: Session,
    identity: RequestIdentity,
    body: BookingCreateRequest,
) -> BookingCreateResponse:
    lock_owner_schedule(session, identity.user_id)
    existing = _find_idempotent_booking(session, identity, body)
    timezone = app_timezone()
    if existing is not None:
        booking, client, service = existing
        return BookingCreateResponse(
            booking=booking_summary(booking, client, service, timezone),
            created=False,
        )

    service = get_active_service(session, identity.user_id, body.service_name)
    client = get_active_client(session, identity.user_id, body.client_public_name)
    reservation = calculate_reservation(service, body.starts_at)
    ensure_reservation_available(session, identity.user_id, reservation)

    now = datetime.now(UTC)
    booking = Booking(
        owner_user_id=identity.user_id,
        client_id=client.id,
        service_id=service.id,
        starts_at=reservation.starts_at,
        ends_at=reservation.ends_at,
        expected_ends_at=reservation.ends_at,
        reserved_starts_at=reservation.reserved_starts_at,
        reserved_ends_at=reservation.reserved_ends_at,
        duration_minutes_snapshot=reservation.duration_minutes,
        buffer_before_minutes_snapshot=reservation.buffer_before_minutes,
        buffer_after_minutes_snapshot=reservation.buffer_after_minutes,
        status=BookingStatus.scheduled,
        price_amount=service.price_amount,
        currency=service.currency,
        price_source="service_snapshot",
        price_confirmed_at=now,
        idempotency_key=body.idempotency_key,
    )
    session.add(booking)
    session.flush()
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="booking.created",
            object_type="booking",
            object_id=booking.id,
            request_id=identity.request_id,
            safe_changes={
                "status": BookingStatus.scheduled.value,
                "duration_minutes": reservation.duration_minutes,
                "buffer_before_minutes": reservation.buffer_before_minutes,
                "buffer_after_minutes": reservation.buffer_after_minutes,
                "currency": service.currency,
            },
        )
    )
    session.commit()
    return BookingCreateResponse(
        booking=booking_summary(booking, client, service, timezone),
        created=True,
    )
