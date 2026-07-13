from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import get_session_factory
from app.models import (
    AuditEvent,
    AvailabilityInterval,
    Booking,
    Client,
    Service,
)


def _save_and_confirm(
    client: TestClient,
    headers: dict[str, str],
    section: str,
    payload: dict,
) -> None:
    saved = client.put(
        f"/api/v1/onboarding/sections/{section}",
        headers=headers,
        json={"payload": payload},
    )
    assert saved.status_code == 200, saved.text
    confirmed = client.post(
        f"/api/v1/onboarding/sections/{section}/confirm",
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text


def _complete_onboarding(client: TestClient, headers: dict[str, str]) -> dict:
    started = client.post("/api/v1/onboarding/start", headers=headers)
    assert started.status_code == 200, started.text

    _save_and_confirm(
        client,
        headers,
        "services",
        {
            "services": [
                {
                    "public_name": "Маникюр",
                    "public_description": "Базовая услуга",
                    "price_amount": "2500.00",
                    "currency": "RUB",
                    "duration_minutes": 120,
                }
            ]
        },
    )
    _save_and_confirm(
        client,
        headers,
        "buffers",
        {
            "buffers": [
                {
                    "service_name": "маникюр",
                    "before_minutes": 5,
                    "after_minutes": 21,
                }
            ]
        },
    )
    _save_and_confirm(
        client,
        headers,
        "availability",
        {
            "days": [
                {
                    "day": "2026-07-15",
                    "is_available": True,
                    "intervals": [
                        {"start_time": "10:00", "end_time": "14:00"},
                        {"start_time": "16:00", "end_time": "20:00"},
                    ],
                    "note": "принимаю по записи",
                },
                {
                    "day": "2026-07-16",
                    "is_available": False,
                    "intervals": [],
                    "note": "не работаю",
                },
            ]
        },
    )
    _save_and_confirm(
        client,
        headers,
        "bookings",
        {
            "bookings": [
                {
                    "client_public_name": "Анна",
                    "client_phone": "+491234567890",
                    "service_name": "МАНИКЮР",
                    "starts_at": "2026-07-15T10:00:00+02:00",
                }
            ]
        },
    )

    completed = client.post("/api/v1/onboarding/complete", headers=headers)
    assert completed.status_code == 200, completed.text
    return completed.json()


@pytest.mark.usefixtures("clean_database")
def test_complete_materializes_confirmed_sections(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    body = _complete_onboarding(client, auth_headers(request_id="materialize-first"))

    assert body["status"] == "completed"
    assert body["current_step"] is None

    with get_session_factory()() as session:
        service = session.scalar(
            select(Service).where(Service.owner_user_id == user.id)
        )
        assert service is not None
        assert service.public_name == "Маникюр"
        assert service.price_amount == Decimal("2500.00")
        assert service.currency == "RUB"
        assert service.duration_minutes == 120
        assert service.buffer_before_minutes == 5
        assert service.buffer_after_minutes == 21
        assert service.is_active is True

        availability = session.scalars(
            select(AvailabilityInterval)
            .where(AvailabilityInterval.owner_user_id == user.id)
            .order_by(
                AvailabilityInterval.day,
                AvailabilityInterval.start_time,
            )
        ).all()
        assert len(availability) == 3
        assert availability[0].day.isoformat() == "2026-07-15"
        assert availability[0].start_time.isoformat() == "10:00:00"
        assert availability[1].start_time.isoformat() == "16:00:00"
        assert availability[2].day.isoformat() == "2026-07-16"
        assert availability[2].is_available is False
        assert availability[2].start_time is None
        assert availability[2].end_time is None

        customer = session.scalar(
            select(Client).where(Client.owner_user_id == user.id)
        )
        assert customer is not None
        assert customer.public_name == "Анна"
        assert customer.normalized_public_name == "анна"
        assert customer.phone == "+491234567890"

        booking = session.scalar(
            select(Booking).where(Booking.owner_user_id == user.id)
        )
        assert booking is not None
        assert booking.client_id == customer.id
        assert booking.service_id == service.id
        assert booking.starts_at.astimezone(UTC) == datetime(
            2026,
            7,
            15,
            8,
            0,
            tzinfo=UTC,
        )
        assert booking.ends_at - booking.starts_at == timedelta(minutes=120)
        assert booking.expected_ends_at == booking.ends_at
        assert booking.price_amount == Decimal("2500.00")
        assert booking.currency == "RUB"
        assert booking.price_source == "onboarding_service_snapshot"
        assert booking.idempotency_key.startswith("onboarding:")

        materialized_audits = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "onboarding.materialized",
            )
        )
        assert materialized_audits == 1


@pytest.mark.usefixtures("clean_database")
def test_repeated_complete_is_idempotent(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers(request_id="materialize-repeat")
    first = _complete_onboarding(client, headers)
    second_response = client.post("/api/v1/onboarding/complete", headers=headers)

    assert second_response.status_code == 200, second_response.text
    assert second_response.json() == first

    with get_session_factory()() as session:
        assert session.scalar(
            select(func.count()).select_from(Service).where(Service.owner_user_id == user.id)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(Client).where(Client.owner_user_id == user.id)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(Booking).where(Booking.owner_user_id == user.id)
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(AvailabilityInterval)
            .where(AvailabilityInterval.owner_user_id == user.id)
        ) == 3
        assert session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "onboarding.materialized",
            )
        ) == 1


@pytest.mark.usefixtures("clean_database")
def test_repeated_complete_preserves_post_onboarding_service_edits(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers(request_id="materialize-preserve-edit")
    _complete_onboarding(client, headers)

    with get_session_factory()() as session:
        service = session.scalar(
            select(Service).where(Service.owner_user_id == user.id)
        )
        assert service is not None
        service.price_amount = Decimal("3000.00")
        service.buffer_after_minutes = 30
        session.commit()

    repeated = client.post("/api/v1/onboarding/complete", headers=headers)
    assert repeated.status_code == 200, repeated.text

    with get_session_factory()() as session:
        service = session.scalar(
            select(Service).where(Service.owner_user_id == user.id)
        )
        assert service is not None
        assert service.price_amount == Decimal("3000.00")
        assert service.buffer_after_minutes == 30
        assert session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "onboarding.materialized",
            )
        ) == 1


@pytest.mark.usefixtures("clean_database")
def test_legacy_completed_onboarding_without_marker_can_be_materialized(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers(request_id="materialize-legacy")
    _complete_onboarding(client, headers)

    with get_session_factory()() as session:
        session.execute(delete(Booking).where(Booking.owner_user_id == user.id))
        session.execute(
            delete(AvailabilityInterval).where(
                AvailabilityInterval.owner_user_id == user.id
            )
        )
        session.execute(delete(Client).where(Client.owner_user_id == user.id))
        session.execute(delete(Service).where(Service.owner_user_id == user.id))
        session.execute(
            delete(AuditEvent).where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "onboarding.materialized",
            )
        )
        session.commit()

    repaired = client.post("/api/v1/onboarding/complete", headers=headers)
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["status"] == "completed"

    with get_session_factory()() as session:
        assert session.scalar(
            select(func.count()).select_from(Service).where(Service.owner_user_id == user.id)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(Client).where(Client.owner_user_id == user.id)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(Booking).where(Booking.owner_user_id == user.id)
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(AvailabilityInterval)
            .where(AvailabilityInterval.owner_user_id == user.id)
        ) == 3
        assert session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "onboarding.materialized",
            )
        ) == 1


@pytest.mark.usefixtures("clean_database")
def test_materialization_is_isolated_per_owner(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    first_user = create_user(telegram_user_id=100000001)
    second_user = create_user(telegram_user_id=100000002)

    _complete_onboarding(
        client,
        auth_headers(
            telegram_user_id=100000001,
            request_id="materialize-owner-one",
        ),
    )
    _complete_onboarding(
        client,
        auth_headers(
            telegram_user_id=100000002,
            request_id="materialize-owner-two",
        ),
    )

    with get_session_factory()() as session:
        for user in (first_user, second_user):
            assert session.scalar(
                select(func.count())
                .select_from(Service)
                .where(Service.owner_user_id == user.id)
            ) == 1
            assert session.scalar(
                select(func.count())
                .select_from(Client)
                .where(Client.owner_user_id == user.id)
            ) == 1
            assert session.scalar(
                select(func.count())
                .select_from(Booking)
                .where(Booking.owner_user_id == user.id)
            ) == 1
            assert session.scalar(
                select(func.count())
                .select_from(AvailabilityInterval)
                .where(AvailabilityInterval.owner_user_id == user.id)
            ) == 3
