from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import (
    AuditEvent,
    Booking,
    BookingStatus,
    Client,
    ClientProfileStatus,
    Service,
)
from app.schemas.scheduling_management import (
    BookingCancelRequest,
    BookingMutationResponse,
    BookingRescheduleRequest,
    BookingSelector,
    ClientCandidateListResponse,
)
from app.services.normalization import normalize_public_name
from app.services.scheduling_common import (
    ReservationTimes,
    SchedulingDomainError,
    app_timezone,
    ensure_reservation_available,
    lock_owner_schedule,
)
from app.services.scheduling_presenters import booking_summary, client_card_summary

_NAME_ALIASES = {
    "аня": "анна",
    "анечка": "анна",
    "маша": "мария",
    "машенька": "мария",
    "настя": "анастасия",
    "настенька": "анастасия",
    "катя": "екатерина",
    "лена": "елена",
    "саша": "александра",
    "наташа": "наталья",
    "оля": "ольга",
    "таня": "татьяна",
    "даша": "дарья",
    "ксюша": "ксения",
    "лиза": "елизавета",
}


def _canonical_first_name(public_name: str) -> str:
    normalized = normalize_public_name(public_name)
    first = normalized.split(" ", 1)[0]
    return _NAME_ALIASES.get(first, first)


def find_client_candidates(
    session: Session,
    identity: RequestIdentity,
    public_name: str,
) -> ClientCandidateListResponse:
    normalized = normalize_public_name(public_name)
    canonical_first = _canonical_first_name(public_name)
    clients = session.scalars(
        select(Client)
        .where(
            Client.owner_user_id == identity.user_id,
            Client.profile_status == ClientProfileStatus.active,
        )
        .order_by(Client.public_name)
    ).all()
    candidates = []
    for client in clients:
        normalized_private_alias = (
            normalize_public_name(client.private_alias) if client.private_alias else None
        )
        if (
            client.normalized_public_name == normalized
            or normalized_private_alias == normalized
        ):
            candidates.append(client)
            continue
        if _canonical_first_name(client.public_name) == canonical_first:
            candidates.append(client)
    return ClientCandidateListResponse(
        candidates=[client_card_summary(client) for client in candidates]
    )


def _find_booking(
    session: Session,
    identity: RequestIdentity,
    selector: BookingSelector,
    *,
    lock: bool,
    allow_cancelled_repeat: bool = False,
) -> tuple[Booking, Client, Service]:
    statement = (
        select(Booking, Client, Service)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.owner_user_id == identity.user_id,
            Client.normalized_public_name
            == normalize_public_name(selector.client_public_name),
            Service.normalized_public_name
            == normalize_public_name(selector.service_name),
            Booking.starts_at == selector.starts_at.astimezone(UTC),
        )
        .order_by(
            Booking.updated_at.desc(),
            Booking.created_at.desc(),
            Booking.id.desc(),
        )
    )
    if lock:
        statement = statement.with_for_update()
    rows = session.execute(statement).all()
    if not rows:
        raise SchedulingDomainError("booking_not_found", status_code=404)

    scheduled_rows = [row for row in rows if row[0].status == BookingStatus.scheduled]
    if len(scheduled_rows) == 1:
        return scheduled_rows[0]
    if len(scheduled_rows) > 1:
        raise SchedulingDomainError("booking_ambiguous")

    if allow_cancelled_repeat:
        for row in rows:
            if row[0].status == BookingStatus.cancelled:
                return row

    if len(rows) == 1:
        return rows[0]
    raise SchedulingDomainError("booking_ambiguous")


def _reservation_from_snapshot(booking: Booking, starts_at: datetime) -> ReservationTimes:
    starts_at_utc = starts_at.astimezone(UTC)
    ends_at = starts_at_utc + timedelta(minutes=booking.duration_minutes_snapshot)
    return ReservationTimes(
        starts_at=starts_at_utc,
        ends_at=ends_at,
        reserved_starts_at=starts_at_utc
        - timedelta(minutes=booking.buffer_before_minutes_snapshot),
        reserved_ends_at=ends_at + timedelta(minutes=booking.buffer_after_minutes_snapshot),
        duration_minutes=booking.duration_minutes_snapshot,
        buffer_before_minutes=booking.buffer_before_minutes_snapshot,
        buffer_after_minutes=booking.buffer_after_minutes_snapshot,
    )


def reschedule_booking(
    session: Session,
    identity: RequestIdentity,
    body: BookingRescheduleRequest,
) -> BookingMutationResponse:
    lock_owner_schedule(session, identity.user_id)
    booking, client, service = _find_booking(session, identity, body, lock=True)
    timezone = app_timezone()
    if booking.status != BookingStatus.scheduled:
        raise SchedulingDomainError("booking_not_scheduled")
    if booking.starts_at.astimezone(UTC) == body.new_starts_at.astimezone(UTC):
        return BookingMutationResponse(
            booking=booking_summary(booking, client, service, timezone),
            changed=False,
        )
    reservation = _reservation_from_snapshot(booking, body.new_starts_at)
    ensure_reservation_available(
        session,
        identity.user_id,
        reservation,
        exclude_booking_id=booking.id,
    )
    previous_start = booking.starts_at
    booking.starts_at = reservation.starts_at
    booking.ends_at = reservation.ends_at
    booking.expected_ends_at = reservation.ends_at
    booking.reserved_starts_at = reservation.reserved_starts_at
    booking.reserved_ends_at = reservation.reserved_ends_at
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="booking.rescheduled",
            object_type="booking",
            object_id=booking.id,
            request_id=identity.request_id,
            safe_changes={
                "from": previous_start.isoformat(),
                "to": booking.starts_at.isoformat(),
                "status": booking.status.value,
            },
        )
    )
    session.commit()
    return BookingMutationResponse(
        booking=booking_summary(booking, client, service, timezone),
        changed=True,
    )


def cancel_booking(
    session: Session,
    identity: RequestIdentity,
    body: BookingCancelRequest,
) -> BookingMutationResponse:
    lock_owner_schedule(session, identity.user_id)
    booking, client, service = _find_booking(
        session,
        identity,
        body,
        lock=True,
        allow_cancelled_repeat=True,
    )
    timezone = app_timezone()
    if booking.status == BookingStatus.cancelled:
        return BookingMutationResponse(
            booking=booking_summary(booking, client, service, timezone),
            changed=False,
        )
    if booking.status != BookingStatus.scheduled:
        raise SchedulingDomainError("booking_not_scheduled")
    booking.status = BookingStatus.cancelled
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="booking.cancelled",
            object_type="booking",
            object_id=booking.id,
            request_id=identity.request_id,
            safe_changes={"status": BookingStatus.cancelled.value},
        )
    )
    session.commit()
    return BookingMutationResponse(
        booking=booking_summary(booking, client, service, timezone),
        changed=True,
    )
