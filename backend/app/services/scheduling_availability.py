from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, AvailabilityInterval, Booking, BookingStatus
from app.schemas.scheduling import (
    AvailabilityDayReplace,
    AvailabilityDayResult,
    AvailabilityReplaceRequest,
    AvailabilityReplaceResponse,
    AvailabilitySummary,
)
from app.services.scheduling_common import (
    SchedulingDomainError,
    app_timezone,
    availability_for_day,
    day_bounds,
    lock_owner_schedule,
)


def _desired_signature(update: AvailabilityDayReplace) -> list[tuple[Any, ...]]:
    if update.state == "unknown":
        return []
    if update.state == "unavailable":
        return [(False, None, None, update.note)]
    return [
        (True, interval.start_time, interval.end_time, update.note)
        for interval in update.intervals
    ]


def _current_signature(rows: list[AvailabilityInterval]) -> list[tuple[Any, ...]]:
    return sorted(
        (row.is_available, row.start_time, row.end_time, row.note)
        for row in rows
    )


def _scheduled_bookings_for_day(
    session: Session,
    identity: RequestIdentity,
    update: AvailabilityDayReplace,
) -> list[Booking]:
    timezone = app_timezone()
    starts_at, ends_at = day_bounds(update.day, timezone)
    return session.scalars(
        select(Booking)
        .where(
            Booking.owner_user_id == identity.user_id,
            Booking.status == BookingStatus.scheduled,
            Booking.reserved_starts_at < ends_at,
            Booking.reserved_ends_at > starts_at,
        )
        .order_by(Booking.starts_at)
        .with_for_update()
    ).all()


def _booking_fits_update(booking: Booking, update: AvailabilityDayReplace) -> bool:
    del booking
    # ADR-006: positive intervals only define suggestion windows. Removing them
    # or changing their boundaries cannot invalidate an explicit booking.
    # Only marking the whole day unavailable conflicts with existing bookings.
    return update.state != "unavailable"


def _validate_booking_safety(
    session: Session,
    identity: RequestIdentity,
    update: AvailabilityDayReplace,
) -> None:
    bookings = _scheduled_bookings_for_day(session, identity, update)
    conflicts = [booking for booking in bookings if not _booking_fits_update(booking, update)]
    if conflicts:
        raise SchedulingDomainError(
            "availability_conflicts_with_bookings",
            details={
                "day": update.day.isoformat(),
                "booking_count": len(conflicts),
            },
        )


def _day_result(
    session: Session,
    identity: RequestIdentity,
    update: AvailabilityDayReplace,
    *,
    changed: bool,
) -> AvailabilityDayResult:
    rows = availability_for_day(session, identity.user_id, update.day)
    return AvailabilityDayResult(
        day=update.day,
        weekday_iso=update.day.isoweekday(),
        availability_known=bool(rows),
        availability=[
            AvailabilitySummary(
                start_time=row.start_time,
                end_time=row.end_time,
                is_available=row.is_available,
                note=row.note,
            )
            for row in rows
        ],
        changed=changed,
    )


def replace_availability(
    session: Session,
    identity: RequestIdentity,
    body: AvailabilityReplaceRequest,
) -> AvailabilityReplaceResponse:
    lock_owner_schedule(session, identity.user_id)

    planned: list[
        tuple[
            AvailabilityDayReplace,
            list[AvailabilityInterval],
            list[tuple[Any, ...]],
            bool,
        ]
    ] = []
    for update in body.days:
        existing = session.scalars(
            select(AvailabilityInterval)
            .where(
                AvailabilityInterval.owner_user_id == identity.user_id,
                AvailabilityInterval.day == update.day,
            )
            .order_by(AvailabilityInterval.start_time)
            .with_for_update()
        ).all()
        desired = _desired_signature(update)
        changed = _current_signature(existing) != sorted(desired)
        if changed:
            _validate_booking_safety(session, identity, update)
        planned.append((update, existing, desired, changed))

    for update, _, desired, changed in planned:
        if not changed:
            continue
        session.execute(
            delete(AvailabilityInterval).where(
                AvailabilityInterval.owner_user_id == identity.user_id,
                AvailabilityInterval.day == update.day,
            )
        )
        for is_available, start_time, end_time, note in desired:
            session.add(
                AvailabilityInterval(
                    owner_user_id=identity.user_id,
                    day=update.day,
                    start_time=start_time,
                    end_time=end_time,
                    is_available=is_available,
                    note=note,
                )
            )
        session.add(
            AuditEvent(
                owner_user_id=identity.user_id,
                actor_user_id=identity.user_id,
                action="availability.replaced",
                object_type="availability_day",
                object_id=None,
                request_id=identity.request_id,
                safe_changes={
                    "day": update.day.isoformat(),
                    "state": update.state,
                    "interval_count": len(update.intervals),
                },
            )
        )

    session.flush()
    results = [
        _day_result(session, identity, update, changed=changed)
        for update, _, _, changed in planned
    ]
    session.commit()
    return AvailabilityReplaceResponse(days=results)
