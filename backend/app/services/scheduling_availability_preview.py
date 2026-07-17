from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AvailabilityInterval, Booking, BookingStatus, Client, Service
from app.schemas.scheduling import (
    AvailabilityDayReplace,
    AvailabilityReplaceRequest,
    AvailabilitySummary,
)
from app.schemas.scheduling_availability import (
    AvailabilityBookingConflict,
    AvailabilityPreviewDay,
    AvailabilityPreviewResponse,
)
from app.services.scheduling_availability import (
    _booking_fits_update,
    _current_signature,
    _desired_signature,
)
from app.services.scheduling_common import app_timezone, day_bounds


def _proposed_availability(update: AvailabilityDayReplace) -> list[AvailabilitySummary]:
    if update.state == "unknown":
        return []
    if update.state == "unavailable":
        return [
            AvailabilitySummary(
                start_time=None,
                end_time=None,
                is_available=False,
                note=update.note,
            )
        ]
    return [
        AvailabilitySummary(
            start_time=interval.start_time,
            end_time=interval.end_time,
            is_available=True,
            note=update.note,
        )
        for interval in update.intervals
    ]


def _preview_day(
    session: Session,
    identity: RequestIdentity,
    update: AvailabilityDayReplace,
) -> AvailabilityPreviewDay:
    existing = session.scalars(
        select(AvailabilityInterval)
        .where(
            AvailabilityInterval.owner_user_id == identity.user_id,
            AvailabilityInterval.day == update.day,
        )
        .order_by(AvailabilityInterval.start_time)
    ).all()
    desired = _desired_signature(update)
    changed = _current_signature(existing) != sorted(desired)

    timezone = app_timezone()
    starts_at, ends_at = day_bounds(update.day, timezone)
    booking_rows = session.execute(
        select(Booking, Client.public_name, Service.public_name)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.owner_user_id == identity.user_id,
            Client.owner_user_id == identity.user_id,
            Service.owner_user_id == identity.user_id,
            Booking.status == BookingStatus.scheduled,
            Booking.reserved_starts_at < ends_at,
            Booking.reserved_ends_at > starts_at,
        )
        .order_by(Booking.starts_at)
    ).all()

    conflicts = [
        AvailabilityBookingConflict(
            client_public_name=client_name,
            service_name=service_name,
            starts_at=booking.starts_at,
            ends_at=booking.ends_at,
            reserved_starts_at=booking.reserved_starts_at,
            reserved_ends_at=booking.reserved_ends_at,
        )
        for booking, client_name, service_name in booking_rows
        if changed and not _booking_fits_update(booking, update)
    ]

    return AvailabilityPreviewDay(
        day=update.day,
        weekday_iso=update.day.isoweekday(),
        availability_known=bool(existing),
        current_availability=[
            AvailabilitySummary(
                start_time=row.start_time,
                end_time=row.end_time,
                is_available=row.is_available,
                note=row.note,
            )
            for row in existing
        ],
        proposed_availability=_proposed_availability(update),
        changed=changed,
        can_apply=not conflicts,
        conflicts=conflicts,
    )


def preview_availability(
    session: Session,
    identity: RequestIdentity,
    body: AvailabilityReplaceRequest,
) -> AvailabilityPreviewResponse:
    return AvailabilityPreviewResponse(
        days=[_preview_day(session, identity, update) for update in body.days]
    )
