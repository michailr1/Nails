from __future__ import annotations

from zoneinfo import ZoneInfo

from app.models import Booking, Client, Service
from app.schemas.scheduling import ClientSummary, DayBookingSummary, ServiceSummary
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


def booking_summary(
    booking: Booking,
    client: Client,
    service: Service,
    timezone: ZoneInfo,
) -> DayBookingSummary:
    return DayBookingSummary(
        id=booking.id,
        client_public_name=client.public_name,
        service_name=service.public_name,
        starts_at=booking.starts_at.astimezone(timezone),
        ends_at=booking.ends_at.astimezone(timezone),
        reserved_starts_at=booking.reserved_starts_at.astimezone(timezone),
        reserved_ends_at=booking.reserved_ends_at.astimezone(timezone),
        status=booking.status,
        price_amount=booking.price_amount,
        currency=booking.currency,
        duration_minutes=booking.duration_minutes_snapshot,
        buffer_before_minutes=booking.buffer_before_minutes_snapshot,
        buffer_after_minutes=booking.buffer_after_minutes_snapshot,
    )
