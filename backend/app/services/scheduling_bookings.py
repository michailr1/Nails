from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, Booking, BookingStatus, Client, Service
from app.schemas.scheduling_catalog_bookings import (
    CatalogBookingCreateRequest,
    CatalogBookingCreateResponse,
)
from app.services.normalization import normalize_public_name
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

_MAX_MONEY = Decimal("9999999999.99")


@dataclass(frozen=True, slots=True)
class CatalogPriceSemantics:
    price_type: str
    price_min: Decimal | None
    price_max: Decimal | None
    price_unit: str | None
    legacy_amount: Decimal
    source: str


def _catalog_item_snapshot(service: Service) -> dict[str, Any]:
    price_amount = (
        str(service.price_amount)
        if service.price_type in {"fixed", "per_unit"}
        else None
    )
    return {
        "service_id": str(service.id),
        "kind": service.kind,
        "public_name": service.public_name,
        "price_type": service.price_type,
        "price_amount": price_amount,
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


def _ensure_money_range(value: Decimal) -> Decimal:
    if value < 0 or value > _MAX_MONEY:
        raise SchedulingDomainError("price_total_out_of_range")
    return value


def _catalog_price_semantics(services: list[Service]) -> CatalogPriceSemantics:
    currencies = {service.currency for service in services}
    if len(currencies) != 1:
        raise SchedulingDomainError("catalog_currency_mismatch")

    if all(service.price_type == "fixed" for service in services):
        total = _ensure_money_range(sum((service.price_amount for service in services), Decimal(0)))
        return CatalogPriceSemantics(
            price_type="fixed",
            price_min=total,
            price_max=total,
            price_unit=None,
            legacy_amount=total,
            source="catalog_fixed",
        )

    if any(service.price_type == "on_request" for service in services):
        return CatalogPriceSemantics(
            price_type="on_request",
            price_min=None,
            price_max=None,
            price_unit=None,
            legacy_amount=Decimal(0),
            source="catalog_on_request",
        )

    per_unit = [service for service in services if service.price_type == "per_unit"]
    if per_unit:
        if len(services) == 1:
            service = per_unit[0]
            return CatalogPriceSemantics(
                price_type="per_unit",
                price_min=service.price_amount,
                price_max=service.price_amount,
                price_unit=service.price_unit,
                legacy_amount=service.price_amount,
                source="catalog_per_unit",
            )
        return CatalogPriceSemantics(
            price_type="on_request",
            price_min=None,
            price_max=None,
            price_unit=None,
            legacy_amount=Decimal(0),
            source="catalog_mixed",
        )

    minimum = Decimal(0)
    maximum = Decimal(0)
    for service in services:
        if service.price_type == "fixed":
            minimum += service.price_amount
            maximum += service.price_amount
        else:
            if service.price_min_amount is None or service.price_max_amount is None:
                raise SchedulingDomainError("invalid_catalog_price")
            minimum += service.price_min_amount
            maximum += service.price_max_amount
    minimum = _ensure_money_range(minimum)
    maximum = _ensure_money_range(maximum)
    return CatalogPriceSemantics(
        price_type="range",
        price_min=minimum,
        price_max=maximum,
        price_unit=None,
        legacy_amount=minimum,
        source="catalog_range",
    )


def _catalog_price_bounds(service: Service) -> tuple[Decimal | None, Decimal | None]:
    semantics = _catalog_price_semantics([service])
    return semantics.price_min, semantics.price_max


def _snapshot_addon_names(booking: Booking) -> list[str]:
    result: list[str] = []
    for item in booking.catalog_items_snapshot:
        if not isinstance(item, dict) or item.get("kind") != "addon":
            continue
        public_name = item.get("public_name")
        if isinstance(public_name, str):
            result.append(normalize_public_name(public_name))
    return sorted(result)


def _find_idempotent_booking(
    session: Session,
    identity: RequestIdentity,
    body: CatalogBookingCreateRequest,
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
    requested_addons = sorted(normalize_public_name(name) for name in body.addon_names)
    price_override_matches = (
        body.price_override_amount is None
        and booking.price_source != "manual_override"
    ) or (
        body.price_override_amount is not None
        and booking.price_source == "manual_override"
        and booking.price_amount == body.price_override_amount
    )
    duration_override_matches = (
        body.duration_override_minutes is None
        and booking.duration_source != "manual_override"
    ) or (
        body.duration_override_minutes is not None
        and booking.duration_source == "manual_override"
        and booking.duration_minutes_snapshot == body.duration_override_minutes
    )
    if (
        client.normalized_public_name != normalize_public_name(body.client_public_name)
        or service.normalized_public_name != normalize_public_name(body.service_name)
        or booking.starts_at.astimezone(UTC) != body.starts_at.astimezone(UTC)
        or _snapshot_addon_names(booking) != requested_addons
        or not price_override_matches
        or not duration_override_matches
    ):
        raise SchedulingDomainError("idempotency_conflict")
    return booking, client, service


def create_booking(
    session: Session,
    identity: RequestIdentity,
    body: CatalogBookingCreateRequest,
) -> CatalogBookingCreateResponse:
    lock_owner_schedule(session, identity.user_id)
    existing = _find_idempotent_booking(session, identity, body)
    timezone = app_timezone()
    if existing is not None:
        booking, client, service = existing
        return CatalogBookingCreateResponse(
            booking=booking_summary(booking, client, service, timezone),
            created=False,
        )

    service = get_active_service(session, identity.user_id, body.service_name)
    addons = get_active_addons(session, identity.user_id, body.addon_names)
    client = get_active_client(session, identity.user_id, body.client_public_name)
    catalog_services = [service, *addons]

    catalog_duration = service.duration_minutes + sum(addon.extra_minutes for addon in addons)
    duration = body.duration_override_minutes or catalog_duration
    reservation = calculate_reservation(
        service,
        body.starts_at,
        duration_minutes=duration,
    )
    ensure_reservation_available(session, identity.user_id, reservation)

    now = datetime.now(UTC)
    semantics = _catalog_price_semantics(catalog_services)
    price_override = body.price_override_amount
    price_amount = (
        _ensure_money_range(price_override)
        if price_override is not None
        else semantics.legacy_amount
    )
    price_source = "manual_override" if price_override is not None else semantics.source
    price_confirmed_at = (
        now
        if price_override is not None or semantics.price_type == "fixed"
        else None
    )
    duration_source = (
        "manual_override" if body.duration_override_minutes is not None else "catalog_v2"
    )

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
        price_amount=price_amount,
        currency=service.currency,
        price_source=price_source,
        price_confirmed_at=price_confirmed_at,
        catalog_items_snapshot=[
            _catalog_item_snapshot(catalog_service)
            for catalog_service in catalog_services
        ],
        catalog_price_type_snapshot=semantics.price_type,
        catalog_price_min_snapshot=semantics.price_min,
        catalog_price_max_snapshot=semantics.price_max,
        catalog_price_unit_snapshot=semantics.price_unit,
        duration_source=duration_source,
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
                "catalog_item_count": len(catalog_services),
                "addon_count": len(addons),
                "catalog_price_type": semantics.price_type,
                "price_source": price_source,
                "duration_source": duration_source,
                "duration_minutes": reservation.duration_minutes,
                "buffer_before_minutes": reservation.buffer_before_minutes,
                "buffer_after_minutes": reservation.buffer_after_minutes,
                "currency": service.currency,
            },
        )
    )
    session.commit()
    return CatalogBookingCreateResponse(
        booking=booking_summary(booking, client, service, timezone),
        created=True,
    )
