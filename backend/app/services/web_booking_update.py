from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, Booking, BookingStatus, Client, Service
from app.schemas.web_booking_update import (
    WebBookingUpdateRequest,
    WebBookingUpdateResponse,
)
from app.services.scheduling_bookings import (
    _catalog_item_snapshot,
    _ensure_money_range,
    CatalogPriceSemantics,
)
from app.services.scheduling_common import (
    SchedulingDomainError,
    app_timezone,
    calculate_reservation,
    ensure_reservation_available,
    lock_owner_schedule,
)
from app.services.scheduling_lookup import (
    get_active_addons,
    get_active_client,
    get_active_service,
)
from app.services.scheduling_presenters import booking_summary
from app.services.web_read import web_booking_summary

_EDITABLE_STATUSES = {BookingStatus.scheduled, BookingStatus.completed}


def _working_price_semantics(services: list[Service]) -> CatalogPriceSemantics:
    currencies = {service.currency for service in services}
    if len(currencies) != 1:
        raise SchedulingDomainError("catalog_currency_mismatch")

    minimum = Decimal(0)
    maximum = Decimal(0)
    estimated = False
    known = False
    for service in services:
        if service.price_type == "fixed":
            minimum += service.price_amount
            maximum += service.price_amount
            known = True
        elif service.price_type == "range":
            if service.price_min_amount is None or service.price_max_amount is None:
                raise SchedulingDomainError("invalid_catalog_price")
            minimum += service.price_min_amount
            maximum += service.price_max_amount
            estimated = True
            known = True
        elif service.price_type == "per_unit":
            minimum += service.price_amount
            maximum += service.price_amount
            estimated = True
            known = True
        else:
            estimated = True

    minimum = _ensure_money_range(minimum)
    maximum = _ensure_money_range(maximum)
    if not known:
        return CatalogPriceSemantics(
            price_type="on_request",
            price_min=None,
            price_max=None,
            price_unit=None,
            legacy_amount=Decimal(0),
            source="catalog_on_request",
        )
    return CatalogPriceSemantics(
        price_type="range" if estimated else "fixed",
        price_min=minimum,
        price_max=maximum,
        price_unit=None,
        legacy_amount=minimum,
        source="catalog_estimate" if estimated else "catalog_fixed",
    )


def update_booking(
    session: Session,
    identity: RequestIdentity,
    booking_id: uuid.UUID,
    body: WebBookingUpdateRequest,
) -> WebBookingUpdateResponse:
    lock_owner_schedule(session, identity.user_id)
    row = session.execute(
        select(Booking, Client, Service)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.id == booking_id,
            Booking.owner_user_id == identity.user_id,
            Client.owner_user_id == identity.user_id,
            Service.owner_user_id == identity.user_id,
        )
        .with_for_update()
    ).first()
    if row is None:
        raise SchedulingDomainError("booking_not_found", status_code=404)

    booking, _old_client, _old_service = row
    if booking.status not in _EDITABLE_STATUSES:
        raise SchedulingDomainError("booking_not_editable")

    client = get_active_client(session, identity.user_id, body.client_public_name)
    service = get_active_service(session, identity.user_id, body.service_name)
    addons = get_active_addons(session, identity.user_id, body.addon_names)
    catalog_services = [service, *addons]
    catalog_duration = service.duration_minutes + sum(
        addon.extra_minutes for addon in addons
    )
    duration = body.duration_override_minutes or catalog_duration
    reservation = calculate_reservation(
        service,
        body.starts_at,
        duration_minutes=duration,
    )
    ensure_reservation_available(
        session,
        identity.user_id,
        reservation,
        exclude_booking_id=booking.id,
    )

    semantics = _working_price_semantics(catalog_services)
    price_override = body.price_override_amount
    price_amount = (
        _ensure_money_range(price_override)
        if price_override is not None
        else semantics.legacy_amount
    )
    price_source = "manual_override" if price_override is not None else semantics.source
    price_confirmed_at = (
        datetime.now(UTC)
        if price_override is not None or semantics.price_type == "fixed"
        else None
    )
    duration_source = (
        "manual_override"
        if body.duration_override_minutes is not None
        else "catalog_v2"
    )
    snapshots = [_catalog_item_snapshot(item) for item in catalog_services]

    before = {
        "client_id": booking.client_id,
        "service_id": booking.service_id,
        "starts_at": booking.starts_at,
        "ends_at": booking.ends_at,
        "price_amount": booking.price_amount,
        "price_source": booking.price_source,
        "duration_minutes": booking.duration_minutes_snapshot,
        "duration_source": booking.duration_source,
        "catalog_items": booking.catalog_items_snapshot,
    }

    booking.client_id = client.id
    booking.service_id = service.id
    booking.starts_at = reservation.starts_at
    booking.ends_at = reservation.ends_at
    booking.expected_ends_at = reservation.ends_at
    booking.reserved_starts_at = reservation.reserved_starts_at
    booking.reserved_ends_at = reservation.reserved_ends_at
    booking.duration_minutes_snapshot = reservation.duration_minutes
    booking.buffer_before_minutes_snapshot = reservation.buffer_before_minutes
    booking.buffer_after_minutes_snapshot = reservation.buffer_after_minutes
    booking.duration_source = duration_source
    booking.price_amount = price_amount
    booking.currency = service.currency
    booking.price_source = price_source
    booking.price_confirmed_at = price_confirmed_at
    booking.catalog_items_snapshot = snapshots
    booking.catalog_price_type_snapshot = semantics.price_type
    booking.catalog_price_min_snapshot = semantics.price_min
    booking.catalog_price_max_snapshot = semantics.price_max
    booking.catalog_price_unit_snapshot = semantics.price_unit

    after = {
        "client_id": booking.client_id,
        "service_id": booking.service_id,
        "starts_at": booking.starts_at,
        "ends_at": booking.ends_at,
        "price_amount": booking.price_amount,
        "price_source": booking.price_source,
        "duration_minutes": booking.duration_minutes_snapshot,
        "duration_source": booking.duration_source,
        "catalog_items": booking.catalog_items_snapshot,
    }
    changed_fields = sorted(key for key in before if before[key] != after[key])

    if changed_fields:
        session.add(
            AuditEvent(
                owner_user_id=identity.user_id,
                actor_user_id=identity.user_id,
                action="booking.updated",
                object_type="booking",
                object_id=booking.id,
                request_id=identity.request_id,
                safe_changes={
                    "changed_fields": changed_fields,
                    "status": booking.status.value,
                    "catalog_item_count": len(catalog_services),
                    "addon_count": len(addons),
                    "price_source": price_source,
                    "duration_source": duration_source,
                    "duration_minutes": reservation.duration_minutes,
                    "currency": service.currency,
                },
            )
        )
        session.commit()

    summary = booking_summary(booking, client, service, app_timezone())
    return WebBookingUpdateResponse(
        booking=web_booking_summary(summary, client_id=client.id),
        changed=bool(changed_fields),
        changed_fields=changed_fields,
    )
