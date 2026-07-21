from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import get_settings
from app.models import Booking, Client, Service
from app.schemas.scheduling_catalog_bookings import CatalogBookingSummary
from app.schemas.web_read import (
    WebCalendarBooking,
    WebCalendarResponse,
    WebClientCard,
    WebClientListResponse,
)
from app.services.scheduling_presenters import booking_summary

_MAX_CALENDAR_DAYS = 31


def _calendar_window(
    date_from: date,
    date_to: date,
) -> tuple[datetime, datetime, str, ZoneInfo]:
    if date_to < date_from:
        raise ValueError("date_to_before_date_from")
    if (date_to - date_from).days + 1 > _MAX_CALENDAR_DAYS:
        raise ValueError("date_range_too_large")
    timezone_name = get_settings().app_timezone
    timezone = ZoneInfo(timezone_name)
    local_start = datetime.combine(date_from, time.min, timezone)
    local_end = datetime.combine(date_to + timedelta(days=1), time.min, timezone)
    return (
        local_start.astimezone(UTC),
        local_end.astimezone(UTC),
        timezone_name,
        timezone,
    )


def web_booking_summary(
    summary: CatalogBookingSummary,
    *,
    client_id: uuid.UUID,
) -> WebCalendarBooking:
    return WebCalendarBooking(
        booking_id=summary.id,
        client_id=client_id,
        client_name=summary.client_public_name,
        service_name=summary.service_name,
        addon_names=summary.addon_names,
        starts_at=summary.starts_at,
        ends_at=summary.ends_at,
        status=summary.status.value,
        price_amount=summary.price_amount,
        currency=summary.currency,
        price_type=summary.price_type,
        price_min_amount=summary.price_min_amount,
        price_max_amount=summary.price_max_amount,
        price_unit=summary.price_unit,
        price_confirmed=summary.price_confirmed,
        duration_minutes=summary.duration_minutes,
    )


def list_calendar(
    session: Session,
    identity: RequestIdentity,
    *,
    date_from: date,
    date_to: date,
) -> WebCalendarResponse:
    starts_at, ends_at, timezone_name, timezone = _calendar_window(
        date_from,
        date_to,
    )
    rows = session.execute(
        select(Booking, Client, Service)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.owner_user_id == identity.user_id,
            Client.owner_user_id == identity.user_id,
            Service.owner_user_id == identity.user_id,
            Booking.starts_at >= starts_at,
            Booking.starts_at < ends_at,
        )
        .order_by(Booking.starts_at, Booking.id)
    ).all()
    return WebCalendarResponse(
        date_from=date_from,
        date_to=date_to,
        timezone=timezone_name,
        bookings=[
            web_booking_summary(
                booking_summary(booking, client, service, timezone),
                client_id=client.id,
            )
            for booking, client, service in rows
        ],
    )


def list_clients(
    session: Session,
    identity: RequestIdentity,
) -> WebClientListResponse:
    clients = session.scalars(
        select(Client)
        .where(Client.owner_user_id == identity.user_id)
        .order_by(Client.public_name, Client.id)
    ).all()
    return WebClientListResponse(
        clients=[
            WebClientCard(
                client_id=client.id,
                public_name=client.public_name,
                phone=client.phone,
                contact_channel=client.contact_channel,
                birthday=client.birthday,
                notes=client.notes,
                nail_skin_notes=client.nail_skin_notes,
                sensitivity_notes=client.sensitivity_notes,
                style_preferences=client.style_preferences,
                communication_preferences=client.communication_preferences,
                profile_status=client.profile_status.value,
                updated_at=client.updated_at,
            )
            for client in clients
        ]
    )
