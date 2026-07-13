from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AvailabilityInterval, Booking, BookingStatus, Service

SLOT_STEP_MINUTES = 15


class SchedulingDomainError(Exception):
    def __init__(
        self,
        code: str,
        *,
        status_code: int = 409,
        details: dict[str, object] | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.details = details


@dataclass(frozen=True, slots=True)
class ReservationTimes:
    starts_at: datetime
    ends_at: datetime
    reserved_starts_at: datetime
    reserved_ends_at: datetime
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int


def app_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def lock_owner_schedule(session: Session, owner_user_id: uuid.UUID) -> None:
    session.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended(:owner_user_id, 0)"
            ")"
        ),
        {"owner_user_id": str(owner_user_id)},
    )


def calculate_reservation(service: Service, starts_at: datetime) -> ReservationTimes:
    starts_at_utc = starts_at.astimezone(UTC)
    ends_at = starts_at_utc + timedelta(minutes=service.duration_minutes)
    reserved_starts_at = starts_at_utc - timedelta(minutes=service.buffer_before_minutes)
    reserved_ends_at = ends_at + timedelta(minutes=service.buffer_after_minutes)
    return ReservationTimes(
        starts_at=starts_at_utc,
        ends_at=ends_at,
        reserved_starts_at=reserved_starts_at,
        reserved_ends_at=reserved_ends_at,
        duration_minutes=service.duration_minutes,
        buffer_before_minutes=service.buffer_before_minutes,
        buffer_after_minutes=service.buffer_after_minutes,
    )


def day_bounds(day: date, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min, tzinfo=timezone)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def availability_for_day(
    session: Session,
    owner_user_id: uuid.UUID,
    day: date,
) -> list[AvailabilityInterval]:
    return session.scalars(
        select(AvailabilityInterval)
        .where(
            AvailabilityInterval.owner_user_id == owner_user_id,
            AvailabilityInterval.day == day,
        )
        .order_by(AvailabilityInterval.start_time)
    ).all()


def overlaps(
    starts_at: datetime,
    ends_at: datetime,
    busy_starts_at: datetime,
    busy_ends_at: datetime,
) -> bool:
    return starts_at < busy_ends_at and ends_at > busy_starts_at


def ceil_to_step(value: datetime, step_minutes: int) -> datetime:
    base = value.replace(second=0, microsecond=0)
    if value.second or value.microsecond:
        base += timedelta(minutes=1)
    remainder = base.minute % step_minutes
    if remainder:
        base += timedelta(minutes=step_minutes - remainder)
    return base


def ensure_reservation_available(
    session: Session,
    owner_user_id: uuid.UUID,
    reservation: ReservationTimes,
    *,
    exclude_booking_id: uuid.UUID | None = None,
) -> None:
    timezone = app_timezone()
    local_reserved_start = reservation.reserved_starts_at.astimezone(timezone)
    local_reserved_end = reservation.reserved_ends_at.astimezone(timezone)
    local_service_start = reservation.starts_at.astimezone(timezone)

    if (
        local_reserved_start.date() != local_service_start.date()
        or local_reserved_end.date() != local_service_start.date()
    ):
        raise SchedulingDomainError("booking_outside_availability")

    availability = availability_for_day(
        session,
        owner_user_id,
        local_service_start.date(),
    )
    if not availability:
        raise SchedulingDomainError("availability_unknown")

    fits = False
    for interval in availability:
        if not interval.is_available or interval.start_time is None or interval.end_time is None:
            continue
        interval_start = datetime.combine(
            local_service_start.date(),
            interval.start_time,
            tzinfo=timezone,
        ).astimezone(UTC)
        interval_end = datetime.combine(
            local_service_start.date(),
            interval.end_time,
            tzinfo=timezone,
        ).astimezone(UTC)
        if (
            reservation.reserved_starts_at >= interval_start
            and reservation.reserved_ends_at <= interval_end
        ):
            fits = True
            break
    if not fits:
        raise SchedulingDomainError("booking_outside_availability")

    statement = select(Booking.id).where(
        Booking.owner_user_id == owner_user_id,
        Booking.status == BookingStatus.scheduled,
        Booking.reserved_starts_at < reservation.reserved_ends_at,
        Booking.reserved_ends_at > reservation.reserved_starts_at,
    )
    if exclude_booking_id is not None:
        statement = statement.where(Booking.id != exclude_booking_id)
    if session.scalar(statement.limit(1)) is not None:
        raise SchedulingDomainError("booking_overlap")
