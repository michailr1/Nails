from __future__ import annotations

from zoneinfo import ZoneInfo

from app.models import Booking, BookingStatus, Client, Service
from app.schemas.scheduling import ClientSummary, ServiceSummary
from app.schemas.scheduling_catalog_bookings import (
    CatalogBookingSummary,
    CatalogItemSummary,
)
from app.schemas.scheduling_management import ClientCardSummary


def service_summary(service: Service) -> ServiceSummary:
    return ServiceSummary(
        id=service.id,
        public_name=service.public_name,
        public_description=service.public_description,
        price_amount=(
            service.price_amount if service.price_type in {"fixed", "per_unit"} else None
        ),
        currency=service.currency,
        duration_minutes=service.duration_minutes if service.kind == "base" else None,
        buffer_before_minutes=service.buffer_before_minutes,
        buffer_after_minutes=service.buffer_after_minutes,
        is_active=service.is_active,
        kind=service.kind,
        price_type=service.price_type,
        price_min_amount=service.price_min_amount,
        price_max_amount=service.price_max_amount,
        price_unit=service.price_unit,
        category=service.category,
        sort_order=service.sort_order,
        extra_minutes=service.extra_minutes,
    )


def client_summary(client: Client) -> ClientSummary:
    return ClientSummary(
        id=client.id,
        public_name=client.public_name,
        phone=client.phone,
    )


def client_card_summary(client: Client) -> ClientCardSummary:
    return ClientCardSummary(
        id=client.id,
        public_name=client.public_name,
        phone=client.phone,
        private_alias=client.private_alias,
        contact_channel=client.contact_channel,
        birthday=client.birthday,
        notes=client.notes,
        nail_skin_notes=client.nail_skin_notes,
        sensitivity_notes=client.sensitivity_notes,
        style_preferences=client.style_preferences,
        communication_preferences=client.communication_preferences,
    )


def _catalog_items(booking: Booking, service: Service) -> list[CatalogItemSummary]:
    raw_items = booking.catalog_items_snapshot
    if not raw_items:
        raw_items = [
            {
                "service_id": str(service.id),
                "kind": "base",
                "public_name": service.public_name,
                "price_type": "fixed",
                "price_amount": str(booking.price_amount),
                "price_min_amount": None,
                "price_max_amount": None,
                "price_unit": None,
                "currency": booking.currency,
                "duration_minutes": booking.duration_minutes_snapshot,
                "extra_minutes": 0,
            }
        ]
    return [CatalogItemSummary.model_validate(item) for item in raw_items]


def _presented_price(booking: Booking):
    if (
        booking.status == BookingStatus.no_show
        or booking.price_source == "final_price_unknown"
    ):
        return None
    if booking.price_source == "final_range_lower_bound_unconfirmed":
        return booking.price_amount
    if (
        booking.price_confirmed_at is not None
        or booking.price_source in {"service_snapshot", "catalog_fixed", "manual_override"}
    ):
        return booking.price_amount
    return None


def _presented_price_source(booking: Booking) -> str:
    if booking.status == BookingStatus.no_show:
        return "final_no_show"
    return booking.price_source


def _presented_price_confirmed(booking: Booking) -> bool:
    return (
        booking.status != BookingStatus.no_show
        and booking.price_confirmed_at is not None
    )


def booking_summary(
    booking: Booking,
    client: Client,
    service: Service,
    timezone: ZoneInfo,
) -> CatalogBookingSummary:
    items = _catalog_items(booking, service)
    return CatalogBookingSummary(
        id=booking.id,
        client_public_name=client.public_name,
        service_name=service.public_name,
        addon_names=[item.public_name for item in items if item.kind == "addon"],
        catalog_items=items,
        starts_at=booking.starts_at.astimezone(timezone),
        ends_at=booking.ends_at.astimezone(timezone),
        reserved_starts_at=booking.reserved_starts_at.astimezone(timezone),
        reserved_ends_at=booking.reserved_ends_at.astimezone(timezone),
        status=booking.status,
        price_amount=_presented_price(booking),
        currency=booking.currency,
        price_type=booking.catalog_price_type_snapshot,
        price_min_amount=booking.catalog_price_min_snapshot,
        price_max_amount=booking.catalog_price_max_snapshot,
        price_unit=booking.catalog_price_unit_snapshot,
        price_source=_presented_price_source(booking),
        price_confirmed=_presented_price_confirmed(booking),
        duration_minutes=booking.duration_minutes_snapshot,
        duration_source=booking.duration_source,
        buffer_before_minutes=booking.buffer_before_minutes_snapshot,
        buffer_after_minutes=booking.buffer_after_minutes_snapshot,
    )
