from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import Booking, BookingStatus, Client, Service
from app.schemas.scheduling import (
    AvailabilitySummary,
    DayViewResponse,
    FreeSlotsResponse,
)
from app.services.scheduling_common import (
    DEFAULT_SUGGESTION_END,
    DEFAULT_SUGGESTION_START,
    SLOT_STEP_MINUTES,
    app_timezone,
    availability_for_day,
    calculate_reservation,
    ceil_to_step,
    day_bounds,
    overlaps,
)
from app.services.scheduling_lookup import get_active_service
from app.services.scheduling_presenters import booking_summary, service_summary


def _bookings_for_range(
    session: Session,
    owner_user_id,
    starts_at: datetime,
    ends_at: datetime,
) -> list[tuple[Booking, Client, Service]]:
    return list(
        session.execute(
            select(Booking, Client, Service)
            .join(Client, Client.id == Booking.client_id)
            .join(Service, Service.id == Booking.service_id)
            .where(
                Booking.owner_user_id == owner_user_id,
                Booking.status != BookingStatus.cancelled,
                Booking.reserved_starts_at < ends_at,
                Booking.reserved_ends_at > starts_at,
            )
            .order_by(Booking.starts_at)
        ).all()
    )


def get_day_view(
    session: Session,
    identity: RequestIdentity,
    day: date,
) -> DayViewResponse:
    timezone = app_timezone()
    start_at, end_at = day_bounds(day, timezone)
    availability = availability_for_day(session, identity.user_id, day)
    bookings = _bookings_for_range(
        session,
        identity.user_id,
        start_at,
        end_at,
    )
    return DayViewResponse(
        day=day,
        timezone=str(timezone),
        weekday_iso=day.isoweekday(),
        availability_known=bool(availability),
        availability=[
            AvailabilitySummary(
                start_time=item.start_time,
                end_time=item.end_time,
                is_available=item.is_available,
                note=item.note,
            )
            for item in availability
        ],
        bookings=[
            booking_summary(booking, client, service, timezone)
            for booking, client, service in bookings
        ],
    )


def find_free_slots(
    session: Session,
    identity: RequestIdentity,
    day: date,
    service_name: str,
) -> FreeSlotsResponse:
    timezone = app_timezone()
    service = get_active_service(session, identity.user_id, service_name)
    availability = availability_for_day(session, identity.user_id, day)
    is_day_off = any(not item.is_available for item in availability)
    explicit_windows = [item for item in availability if item.is_available]

    if is_day_off:
        suggestion_windows = []
    elif explicit_windows:
        suggestion_windows = [
            (item.start_time, item.end_time)
            for item in explicit_windows
            if item.start_time is not None and item.end_time is not None
        ]
    else:
        suggestion_windows = [(DEFAULT_SUGGESTION_START, DEFAULT_SUGGESTION_END)]

    start_at, end_at = day_bounds(day, timezone)
    busy = [
        (booking.reserved_starts_at, booking.reserved_ends_at)
        for booking, _, _ in _bookings_for_range(
            session,
            identity.user_id,
            start_at,
            end_at,
        )
        if booking.status == BookingStatus.scheduled
    ]

    starts: set[datetime] = set()
    for start_time, end_time in suggestion_windows:
        interval_start = datetime.combine(day, start_time, tzinfo=timezone)
        interval_end = datetime.combine(day, end_time, tzinfo=timezone)
        candidate = ceil_to_step(
            interval_start + timedelta(minutes=service.buffer_before_minutes),
            SLOT_STEP_MINUTES,
        )
        last_start = interval_end - timedelta(
            minutes=service.duration_minutes + service.buffer_after_minutes
        )
        while candidate <= last_start:
            reservation = calculate_reservation(service, candidate)
            if not any(
                overlaps(
                    reservation.reserved_starts_at,
                    reservation.reserved_ends_at,
                    busy_start,
                    busy_end,
                )
                for busy_start, busy_end in busy
            ):
                starts.add(candidate)
            candidate += timedelta(minutes=SLOT_STEP_MINUTES)

    return FreeSlotsResponse(
        day=day,
        timezone=str(timezone),
        weekday_iso=day.isoweekday(),
        availability_known=bool(availability),
        is_working=not is_day_off,
        step_minutes=SLOT_STEP_MINUTES,
        service=service_summary(service),
        starts_at=sorted(starts),
    )
