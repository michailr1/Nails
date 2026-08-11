from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    AvailabilityInterval,
    Booking,
    BookingStatus,
    Client,
    Service,
)
from app.models_preferences import MasterPreferences
from app.timezones import owner_timezone

SLOT_STEP_MINUTES = 15
DEFAULT_SUGGESTION_START = time(10)
DEFAULT_SUGGESTION_END = time(23)


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


def calculate_reservation(
    service: Service,
    starts_at: datetime,
    *,
    duration_minutes: int | None = None,
) -> ReservationTimes:
    effective_duration = (
        service.duration_minutes if duration_minutes is None else duration_minutes
    )
    if effective_duration < 1 or effective_duration > 1440:
        raise SchedulingDomainError("duration_out_of_range")

    starts_at_utc = starts_at.astimezone(UTC)
    ends_at = starts_at_utc + timedelta(minutes=effective_duration)
    reserved_starts_at = starts_at_utc - timedelta(minutes=service.buffer_before_minutes)
    reserved_ends_at = ends_at + timedelta(minutes=service.buffer_after_minutes)
    return ReservationTimes(
        starts_at=starts_at_utc,
        ends_at=ends_at,
        reserved_starts_at=reserved_starts_at,
        reserved_ends_at=reserved_ends_at,
        duration_minutes=effective_duration,
        buffer_before_minutes=service.buffer_before_minutes,
        buffer_after_minutes=service.buffer_after_minutes,
    )


def is_representable_local_datetime(value: datetime) -> bool:
    """Return false for local wall times skipped by a timezone transition."""
    if value.tzinfo is None:
        return False
    round_trip = value.astimezone(UTC).astimezone(value.tzinfo)
    return round_trip.replace(fold=value.fold) == value


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


def _usual_work_windows(
    session: Session,
    owner_user_id: uuid.UUID,
) -> list[tuple[time, time]]:
    preferences = session.scalar(
        select(MasterPreferences).where(MasterPreferences.user_id == owner_user_id)
    )
    raw_intervals = preferences.default_work_intervals if preferences is not None else None
    windows: list[tuple[time, time]] = []
    for item in raw_intervals or []:
        if not isinstance(item, dict):
            continue
        start_value = item.get("start_time")
        end_value = item.get("end_time")
        if not isinstance(start_value, str) or not isinstance(end_value, str):
            continue
        try:
            start_time = time.fromisoformat(start_value)
            end_time = time.fromisoformat(end_value)
        except ValueError:
            continue
        if start_time < end_time:
            windows.append((start_time, end_time))
    return windows


def suggestion_windows_for_day(
    session: Session,
    owner_user_id: uuid.UUID,
    day: date,
) -> tuple[list[tuple[time, time]], bool]:
    """Resolve ADR-006 suggestion windows: date override -> usual hours -> fallback.

    The returned boolean is the whole-day day-off marker. Positive windows only
    shape suggestions and never turn into a hard booking restriction.
    """
    availability = availability_for_day(session, owner_user_id, day)
    if any(not item.is_available for item in availability):
        return [], True

    explicit_windows = [
        (item.start_time, item.end_time)
        for item in availability
        if item.is_available and item.start_time is not None and item.end_time is not None
    ]
    if explicit_windows:
        return explicit_windows, False

    usual_windows = _usual_work_windows(session, owner_user_id)
    if usual_windows:
        return usual_windows, False

    return [(DEFAULT_SUGGESTION_START, DEFAULT_SUGGESTION_END)], False


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


def _booking_addon_names(booking: Booking) -> list[str]:
    addon_names: list[str] = []
    for item in booking.catalog_items_snapshot or []:
        if not isinstance(item, dict) or item.get("kind") != "addon":
            continue
        public_name = item.get("public_name")
        if isinstance(public_name, str) and public_name.strip():
            addon_names.append(public_name.strip())
    return addon_names


def _booking_conflict_details(
    booking: Booking,
    client: Client,
    service: Service,
) -> dict[str, object]:
    return {
        "client_name": client.public_name,
        "service_name": service.public_name,
        "addon_names": _booking_addon_names(booking),
        "starts_at": booking.starts_at.astimezone(UTC).isoformat(),
        "ends_at": booking.ends_at.astimezone(UTC).isoformat(),
        "reserved_starts_at": booking.reserved_starts_at.astimezone(UTC).isoformat(),
        "reserved_ends_at": booking.reserved_ends_at.astimezone(UTC).isoformat(),
    }


def ensure_reservation_available(
    session: Session,
    owner_user_id: uuid.UUID,
    reservation: ReservationTimes,
    *,
    exclude_booking_id: uuid.UUID | None = None,
) -> None:
    timezone = owner_timezone(session, owner_user_id)
    service_day = reservation.starts_at.astimezone(timezone).date()
    availability = availability_for_day(session, owner_user_id, service_day)

    # ADR-006: explicit booking is open by default. A false row is the existing
    # whole-day day-off marker. Positive intervals only bound suggested slots;
    # usual hours and fallback windows likewise never gate an explicit booking.
    if any(not interval.is_available for interval in availability):
        raise SchedulingDomainError("booking_on_day_off")

    statement = (
        select(Booking, Client, Service)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.owner_user_id == owner_user_id,
            Client.owner_user_id == owner_user_id,
            Service.owner_user_id == owner_user_id,
            Booking.status == BookingStatus.scheduled,
            Booking.reserved_starts_at < reservation.reserved_ends_at,
            Booking.reserved_ends_at > reservation.reserved_starts_at,
        )
        .order_by(Booking.starts_at, Booking.id)
    )
    if exclude_booking_id is not None:
        statement = statement.where(Booking.id != exclude_booking_id)
    conflicts = session.execute(statement).all()
    if conflicts:
        raise SchedulingDomainError(
            "booking_overlap",
            details={
                "conflicts": [
                    _booking_conflict_details(booking, client, service)
                    for booking, client, service in conflicts
                ]
            },
        )
