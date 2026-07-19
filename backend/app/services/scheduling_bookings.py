from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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


def _catalog_item_snapshot(service: Service) -> dict[str, Any]:
    return {
        "service_id": str(service.id),
        "kind": service.kind,
        "public_name": service.public_name,
        "price_type": service.price_type,
        "price_amount": str(service.price_amount) if service.price_type in {"fixed", "per_unit"} else None,
        "price_min_amount": (
            str(service.price_min_amount) if service.price_min_amount is not None else None
        ),
        "price_max_amount": (
            str(service.price_max_amount) if service.price_max_amount is not None else None
        ),
        "price_unit": service.price_unit,
        "currency": service.currency,
        "duration_minutes": service.duration_minutes if service.kind == "base" else None,
        "extra_minutes": service.extra_minutes,
    }


def _catalog_price_bounds(service: Service) -> tuple[Decimal | None, Decimal | None]:
    if service.price_type in {"fixed", "per_unit"}:
        return service.price_amount, service.price_amount
    if service.price_type == "range":
        return service.price_min_amount, service.price_max_amount
    return None, None


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
    price_min, price_max = _catalog_price_bounds(service)
    price_confirmed_at = now if service.price_type == "fixed" else None
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
        price_confirmed_at=price_confirmed_at,
        catalog_items_snapshot=[_catalog_item_snapshot(service)],
        catalog_price_type_snapshot=service.price_type,
        catalog_price_min_snapshot=price_min,
        catalog_price_max_snapshot=price_max,
        catalog_price_unit_snapshot=service.price_unit,
        duration_source="catalog_snapshot",
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
                "catalog_item_count": 1,
                "catalog_price_type": service.price_type,
                "duration_source": booking.duration_source,
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
