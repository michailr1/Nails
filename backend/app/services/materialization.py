from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import (
    AuditEvent,
    AvailabilityInterval,
    Booking,
    BookingStatus,
    Client,
    ClientProfileStatus,
    OnboardingDraft,
    OnboardingSection,
    OnboardingState,
    OnboardingStatus,
    Service,
)
from app.services.normalization import normalize_public_name


class MaterializationError(Exception):
    def __init__(self, code: str, details: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.details = details


@dataclass(slots=True)
class MaterializationSummary:
    services_created: int = 0
    services_updated: int = 0
    availability_days_replaced: int = 0
    clients_created: int = 0
    clients_updated: int = 0
    bookings_created: int = 0

    @property
    def changed(self) -> bool:
        return any(self.as_safe_changes().values())

    def as_safe_changes(self) -> dict[str, int]:
        return {
            "services_created": self.services_created,
            "services_updated": self.services_updated,
            "availability_days_replaced": self.availability_days_replaced,
            "clients_created": self.clients_created,
            "clients_updated": self.clients_updated,
            "bookings_created": self.bookings_created,
        }


def _was_materialized(
    session: Session,
    identity: RequestIdentity,
    state: OnboardingState,
) -> bool:
    marker = session.scalar(
        select(AuditEvent.id)
        .where(
            AuditEvent.owner_user_id == identity.user_id,
            AuditEvent.object_id == state.id,
            AuditEvent.action == "onboarding.materialized",
        )
        .limit(1)
    )
    return marker is not None


def _confirmed_drafts(state: OnboardingState) -> dict[OnboardingSection, OnboardingDraft]:
    drafts = {draft.section: draft for draft in state.drafts}
    missing = [
        section.value
        for section in OnboardingSection
        if section not in drafts
        or not drafts[section].is_confirmed
        or drafts[section].confirmed_revision != drafts[section].revision
        or drafts[section].confirmed_payload is None
    ]
    if missing:
        raise MaterializationError(
            "onboarding_sections_not_confirmed",
            details={"sections": missing},
        )
    return drafts


def _index_services(
    session: Session,
    owner_user_id: uuid.UUID,
) -> dict[str, Service]:
    services = session.scalars(
        select(Service)
        .where(Service.owner_user_id == owner_user_id)
        .with_for_update()
    ).all()
    indexed: dict[str, Service] = {}
    for service in services:
        key = normalize_public_name(service.public_name)
        if key in indexed:
            raise MaterializationError("duplicate_service_lookup_key")
        indexed[key] = service
    return indexed


def _materialize_services(
    session: Session,
    identity: RequestIdentity,
    drafts: dict[OnboardingSection, OnboardingDraft],
    summary: MaterializationSummary,
) -> dict[str, Service]:
    services_payload = drafts[OnboardingSection.services].confirmed_payload or {}
    buffers_payload = drafts[OnboardingSection.buffers].confirmed_payload or {}
    buffers = {
        normalize_public_name(item["service_name"]): item
        for item in buffers_payload.get("buffers", [])
    }
    indexed = _index_services(session, identity.user_id)

    for item in services_payload.get("services", []):
        key = normalize_public_name(item["public_name"])
        buffer = buffers.get(key, {})
        desired = {
            "public_name": item["public_name"],
            "public_description": item.get("public_description"),
            "price_amount": Decimal(str(item["price_amount"])),
            "currency": item["currency"],
            "duration_minutes": item["duration_minutes"],
            "buffer_before_minutes": buffer.get("before_minutes", 0),
            "buffer_after_minutes": buffer.get("after_minutes", 0),
            "is_active": True,
        }
        service = indexed.get(key)
        if service is None:
            service = Service(owner_user_id=identity.user_id, **desired)
            session.add(service)
            indexed[key] = service
            summary.services_created += 1
            continue

        changed = False
        for field, value in desired.items():
            if getattr(service, field) != value:
                setattr(service, field, value)
                changed = True
        if changed:
            summary.services_updated += 1

    session.flush()
    return indexed


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def _parse_time(value: str) -> time:
    return time.fromisoformat(value)


def _desired_availability_signature(day_payload: dict[str, Any]) -> list[tuple[Any, ...]]:
    note = day_payload.get("note")
    if not day_payload["is_available"]:
        return [(False, None, None, note)]
    return [
        (
            True,
            _parse_time(interval["start_time"]),
            _parse_time(interval["end_time"]),
            note,
        )
        for interval in day_payload.get("intervals", [])
    ]


def _current_availability_signature(
    rows: list[AvailabilityInterval],
) -> list[tuple[Any, ...]]:
    return sorted(
        (
            row.is_available,
            row.start_time,
            row.end_time,
            row.note,
        )
        for row in rows
    )


def _materialize_availability(
    session: Session,
    identity: RequestIdentity,
    drafts: dict[OnboardingSection, OnboardingDraft],
    summary: MaterializationSummary,
) -> None:
    payload = drafts[OnboardingSection.availability].confirmed_payload or {}
    for day_payload in payload.get("days", []):
        day = _parse_day(day_payload["day"])
        existing = session.scalars(
            select(AvailabilityInterval)
            .where(
                AvailabilityInterval.owner_user_id == identity.user_id,
                AvailabilityInterval.day == day,
            )
            .with_for_update()
        ).all()
        desired_signature = _desired_availability_signature(day_payload)
        if _current_availability_signature(existing) == sorted(desired_signature):
            continue

        session.execute(
            delete(AvailabilityInterval).where(
                AvailabilityInterval.owner_user_id == identity.user_id,
                AvailabilityInterval.day == day,
            )
        )
        for is_available, start_time, end_time, note in desired_signature:
            session.add(
                AvailabilityInterval(
                    owner_user_id=identity.user_id,
                    day=day,
                    start_time=start_time,
                    end_time=end_time,
                    is_available=is_available,
                    note=note,
                )
            )
        summary.availability_days_replaced += 1


def _index_active_clients(
    session: Session,
    owner_user_id: uuid.UUID,
) -> dict[str, Client]:
    clients = session.scalars(
        select(Client)
        .where(
            Client.owner_user_id == owner_user_id,
            Client.profile_status == ClientProfileStatus.active,
        )
        .with_for_update()
    ).all()
    indexed: dict[str, Client] = {}
    for client in clients:
        key = client.normalized_public_name
        if key in indexed:
            raise MaterializationError("duplicate_client_lookup_key")
        indexed[key] = client
    return indexed


def _resolve_client(
    session: Session,
    identity: RequestIdentity,
    indexed: dict[str, Client],
    booking_payload: dict[str, Any],
    booking_index: int,
    summary: MaterializationSummary,
) -> Client:
    public_name = booking_payload["client_public_name"]
    normalized = normalize_public_name(public_name)
    phone = booking_payload.get("client_phone")
    client = indexed.get(normalized)
    if client is None:
        client = Client(
            owner_user_id=identity.user_id,
            public_name=public_name,
            normalized_public_name=normalized,
            phone=phone,
            profile_status=ClientProfileStatus.active,
        )
        session.add(client)
        session.flush()
        indexed[normalized] = client
        summary.clients_created += 1
        return client

    if phone and client.phone and client.phone != phone:
        raise MaterializationError(
            "client_contact_conflict",
            details={"booking_index": booking_index},
        )
    if phone and client.phone is None:
        client.phone = phone
        summary.clients_updated += 1
    return client


def _booking_key(
    state: OnboardingState,
    booking_draft: OnboardingDraft,
    booking_index: int,
) -> str:
    return (
        f"onboarding:{state.id}:"
        f"{booking_draft.confirmed_revision}:{booking_index}"
    )


def _as_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(UTC)


def _booking_matches(
    booking: Booking,
    *,
    client: Client,
    service: Service,
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    return all(
        (
            booking.client_id == client.id,
            booking.service_id == service.id,
            booking.starts_at.astimezone(UTC) == starts_at,
            booking.ends_at.astimezone(UTC) == ends_at,
            booking.price_amount == service.price_amount,
            booking.currency == service.currency,
        )
    )


def _materialize_bookings(
    session: Session,
    identity: RequestIdentity,
    state: OnboardingState,
    drafts: dict[OnboardingSection, OnboardingDraft],
    services: dict[str, Service],
    summary: MaterializationSummary,
    materialized_at: datetime,
) -> None:
    booking_draft = drafts[OnboardingSection.bookings]
    payload = booking_draft.confirmed_payload or {}
    bookings_payload = payload.get("bookings", [])
    clients = _index_active_clients(session, identity.user_id)
    keys = [
        _booking_key(state, booking_draft, index)
        for index in range(len(bookings_payload))
    ]
    existing_by_key = {
        booking.idempotency_key: booking
        for booking in session.scalars(
            select(Booking)
            .where(
                Booking.owner_user_id == identity.user_id,
                Booking.idempotency_key.in_(keys),
            )
            .with_for_update()
        ).all()
    }

    for index, item in enumerate(bookings_payload):
        service = services.get(normalize_public_name(item["service_name"]))
        if service is None:
            raise MaterializationError(
                "materialization_service_missing",
                details={"booking_index": index},
            )
        client = _resolve_client(session, identity, clients, item, index, summary)
        starts_at = _as_utc(item["starts_at"])
        ends_at = starts_at + timedelta(minutes=service.duration_minutes)
        idempotency_key = keys[index]
        existing = existing_by_key.get(idempotency_key)
        if existing is not None:
            if not _booking_matches(
                existing,
                client=client,
                service=service,
                starts_at=starts_at,
                ends_at=ends_at,
            ):
                raise MaterializationError(
                    "materialized_booking_conflict",
                    details={"booking_index": index},
                )
            continue

        booking = Booking(
            owner_user_id=identity.user_id,
            client_id=client.id,
            service_id=service.id,
            starts_at=starts_at,
            ends_at=ends_at,
            expected_ends_at=ends_at,
            status=BookingStatus.scheduled,
            price_amount=service.price_amount,
            currency=service.currency,
            price_source="onboarding_service_snapshot",
            price_confirmed_at=materialized_at,
            idempotency_key=idempotency_key,
        )
        session.add(booking)
        summary.bookings_created += 1


def materialize_confirmed_onboarding(
    session: Session,
    identity: RequestIdentity,
    state: OnboardingState,
) -> MaterializationSummary:
    """Materialize confirmed onboarding data without committing the transaction."""

    if state.status == OnboardingStatus.completed and _was_materialized(
        session,
        identity,
        state,
    ):
        return MaterializationSummary()

    drafts = _confirmed_drafts(state)
    summary = MaterializationSummary()
    materialized_at = datetime.now(UTC)
    services = _materialize_services(session, identity, drafts, summary)
    _materialize_availability(session, identity, drafts, summary)
    _materialize_bookings(
        session,
        identity,
        state,
        drafts,
        services,
        summary,
        materialized_at,
    )
    session.flush()

    if summary.changed:
        session.add(
            AuditEvent(
                owner_user_id=identity.user_id,
                actor_user_id=identity.user_id,
                action="onboarding.materialized",
                object_type="onboarding_state",
                object_id=state.id,
                request_id=identity.request_id,
                safe_changes=summary.as_safe_changes(),
            )
        )
    return summary
