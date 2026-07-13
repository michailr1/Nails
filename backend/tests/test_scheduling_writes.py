from collections.abc import Callable
from datetime import date, time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import get_session_factory
from app.models import AuditEvent, Booking, Service


def _create_client(
    client: TestClient,
    headers: dict[str, str],
    *,
    public_name: str = "Анна",
    phone: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/scheduling/clients",
        headers=headers,
        json={"public_name": public_name, "phone": phone},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_booking(
    client: TestClient,
    headers: dict[str, str],
    *,
    starts_at: str = "2026-07-18T13:00:00+02:00",
    idempotency_key: str = "booking-create-001",
    client_public_name: str = "Анна",
    service_name: str = "Маникюр",
):
    return client.post(
        "/api/v1/scheduling/bookings",
        headers=headers,
        json={
            "client_public_name": client_public_name,
            "service_name": service_name,
            "starts_at": starts_at,
            "idempotency_key": idempotency_key,
        },
    )


@pytest.mark.usefixtures("clean_database")
def test_client_creation_is_normalized_idempotent_and_contact_safe(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers(request_id="client-create")

    first = _create_client(
        client,
        headers,
        public_name="  Анна  ",
    )
    assert first["created"] is True
    assert first["contact_added"] is False

    reused = _create_client(
        client,
        headers,
        public_name="АННА",
        phone="+491234567890",
    )
    assert reused["created"] is False
    assert reused["contact_added"] is True
    assert reused["client"]["phone"] == "+491234567890"
    assert reused["client"]["id"] == first["client"]["id"]

    conflict = client.post(
        "/api/v1/scheduling/clients",
        headers=headers,
        json={"public_name": "анна", "phone": "+499999999999"},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "client_contact_conflict"

    with get_session_factory()() as session:
        assert session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "client.created",
            )
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "client.contact_added",
            )
        ) == 1


@pytest.mark.usefixtures("clean_database")
def test_booking_creation_snapshots_service_and_is_idempotent(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    service = create_service(
        user.id,
        price_amount=Decimal("2500.00"),
        duration_minutes=120,
        buffer_before_minutes=5,
        buffer_after_minutes=21,
    )
    create_availability(
        user.id,
        day=date(2026, 7, 18),
        start_time=time(11, 0),
        end_time=time(20, 0),
    )
    headers = auth_headers(request_id="booking-create")
    _create_client(client, headers)

    created = _create_booking(client, headers)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["created"] is True
    booking = body["booking"]
    assert booking["starts_at"] == "2026-07-18T13:00:00+02:00"
    assert booking["ends_at"] == "2026-07-18T15:00:00+02:00"
    assert booking["reserved_starts_at"] == "2026-07-18T12:55:00+02:00"
    assert booking["reserved_ends_at"] == "2026-07-18T15:21:00+02:00"
    assert booking["duration_minutes"] == 120
    assert booking["buffer_before_minutes"] == 5
    assert booking["buffer_after_minutes"] == 21
    assert booking["price_amount"] == "2500.00"
    assert booking["currency"] == "RUB"

    repeated = _create_booking(client, headers)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["created"] is False
    assert repeated.json()["booking"]["id"] == booking["id"]

    with get_session_factory()() as session:
        assert session.scalar(
            select(func.count()).select_from(Booking).where(
                Booking.owner_user_id == user.id
            )
        ) == 1
        stored_service = session.get(Service, service.id)
        assert stored_service is not None
        stored_service.price_amount = Decimal("3100.00")
        stored_service.duration_minutes = 60
        stored_service.buffer_before_minutes = 0
        stored_service.buffer_after_minutes = 0
        session.commit()

    day_view = client.get(
        "/api/v1/scheduling/day",
        headers=headers,
        params={"day": "2026-07-18"},
    )
    assert day_view.status_code == 200, day_view.text
    saved = day_view.json()["bookings"][0]
    assert saved["price_amount"] == "2500.00"
    assert saved["duration_minutes"] == 120
    assert saved["buffer_before_minutes"] == 5
    assert saved["buffer_after_minutes"] == 21
    assert saved["reserved_ends_at"] == "2026-07-18T15:21:00+02:00"

    slots = client.get(
        "/api/v1/scheduling/slots",
        headers=headers,
        params={"day": "2026-07-18", "service_name": "Маникюр"},
    )
    assert slots.status_code == 200, slots.text
    assert "2026-07-18T15:15:00+02:00" not in slots.json()["starts_at"]
    assert "2026-07-18T15:30:00+02:00" in slots.json()["starts_at"]


@pytest.mark.usefixtures("clean_database")
def test_booking_rejects_overlap_outside_hours_unknown_day_and_key_conflict(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id)
    create_availability(
        user.id,
        day=date(2026, 7, 18),
        start_time=time(11, 0),
        end_time=time(20, 0),
    )
    headers = auth_headers(request_id="booking-errors")
    _create_client(client, headers, public_name="Анна")
    _create_client(client, headers, public_name="Мария")

    first = _create_booking(client, headers)
    assert first.status_code == 200, first.text

    overlap = _create_booking(
        client,
        headers,
        client_public_name="Мария",
        starts_at="2026-07-18T15:15:00+02:00",
        idempotency_key="booking-overlap",
    )
    assert overlap.status_code == 409, overlap.text
    assert overlap.json()["detail"]["code"] == "booking_overlap"

    outside = _create_booking(
        client,
        headers,
        client_public_name="Мария",
        starts_at="2026-07-18T10:45:00+02:00",
        idempotency_key="booking-outside",
    )
    assert outside.status_code == 409, outside.text
    assert outside.json()["detail"]["code"] == "booking_outside_availability"

    unknown = _create_booking(
        client,
        headers,
        client_public_name="Мария",
        starts_at="2026-07-19T13:00:00+02:00",
        idempotency_key="booking-unknown-day",
    )
    assert unknown.status_code == 409, unknown.text
    assert unknown.json()["detail"]["code"] == "availability_unknown"

    key_conflict = _create_booking(
        client,
        headers,
        starts_at="2026-07-18T16:00:00+02:00",
        idempotency_key="booking-create-001",
    )
    assert key_conflict.status_code == 409, key_conflict.text
    assert key_conflict.json()["detail"]["code"] == "idempotency_conflict"


@pytest.mark.usefixtures("clean_database")
def test_same_time_is_isolated_between_owners(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    for telegram_id in (100000001, 100000002):
        user = create_user(telegram_user_id=telegram_id)
        create_service(user.id)
        create_availability(user.id)
        headers = auth_headers(
            telegram_user_id=telegram_id,
            request_id=f"owner-{telegram_id}",
        )
        _create_client(client, headers)
        response = _create_booking(
            client,
            headers,
            idempotency_key=f"booking-{telegram_id}",
        )
        assert response.status_code == 200, response.text
        assert response.json()["created"] is True
