from collections.abc import Callable
from datetime import date, time

import pytest
from fastapi.testclient import TestClient


def _create_booking(
    client: TestClient,
    auth_headers: Callable,
    *,
    client_name: str = "Анна Тестовая",
    starts_at: str = "2026-07-17T11:00:00+02:00",
) -> dict:
    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id="client-create"),
        json={"public_name": client_name, "phone": None},
    )
    assert created_client.status_code == 200, created_client.text
    booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="booking-create"),
        json={
            "client_public_name": client_name,
            "service_name": "Маникюр",
            "starts_at": starts_at,
            "idempotency_key": f"booking-{client_name}-{starts_at}",
        },
    )
    assert booking.status_code == 200, booking.text
    return booking.json()["booking"]


@pytest.mark.usefixtures("clean_database")
def test_client_candidates_match_diminutive_without_cross_owner_leak(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user(telegram_user_id=1001)
    create_user(telegram_user_id=2002)
    first_headers = auth_headers(telegram_user_id=1001)
    second_headers = auth_headers(telegram_user_id=2002)

    assert client.post(
        "/api/v1/scheduling/clients",
        headers=first_headers,
        json={"public_name": "Анна Тестовая", "phone": None},
    ).status_code == 200
    assert client.post(
        "/api/v1/scheduling/clients",
        headers=second_headers,
        json={"public_name": "Анна Чужая", "phone": None},
    ).status_code == 200

    response = client.get(
        "/api/v1/scheduling/clients/candidates",
        headers=first_headers,
        params={"public_name": "Аня"},
    )
    assert response.status_code == 200, response.text
    assert [item["public_name"] for item in response.json()["candidates"]] == [
        "Анна Тестовая"
    ]


@pytest.mark.usefixtures("clean_database")
def test_booking_can_be_rescheduled_with_snapshots_preserved_and_repeat_is_safe(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id, price_amount="2700.00", duration_minutes=120, buffer_after_minutes=21)
    create_availability(user.id, day=date(2026, 7, 17), start_time=time(11), end_time=time(18))
    original = _create_booking(client, auth_headers)

    payload = {
        "client_public_name": "Анна Тестовая",
        "service_name": "Маникюр",
        "starts_at": "2026-07-17T11:00:00+02:00",
        "new_starts_at": "2026-07-17T14:00:00+02:00",
    }
    moved = client.put(
        "/api/v1/scheduling/bookings/reschedule",
        headers=auth_headers(request_id="booking-move"),
        json=payload,
    )
    assert moved.status_code == 200, moved.text
    result = moved.json()
    assert result["changed"] is True
    assert result["booking"]["starts_at"].startswith("2026-07-17T14:00:00")
    assert result["booking"]["price_amount"] == original["price_amount"] == "2700.00"
    assert result["booking"]["duration_minutes"] == original["duration_minutes"] == 120
    assert result["booking"]["buffer_after_minutes"] == 21

    repeated = client.put(
        "/api/v1/scheduling/bookings/reschedule",
        headers=auth_headers(request_id="booking-move-repeat"),
        json={**payload, "starts_at": payload["new_starts_at"]},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["changed"] is False


@pytest.mark.usefixtures("clean_database")
def test_booking_cancel_is_soft_idempotent_and_frees_slot(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id, price_amount="2700.00", duration_minutes=120, buffer_after_minutes=21)
    create_availability(user.id, day=date(2026, 7, 17), start_time=time(11), end_time=time(18))
    _create_booking(client, auth_headers)

    payload = {
        "client_public_name": "Анна Тестовая",
        "service_name": "Маникюр",
        "starts_at": "2026-07-17T11:00:00+02:00",
    }
    cancelled = client.put(
        "/api/v1/scheduling/bookings/cancel",
        headers=auth_headers(request_id="booking-cancel"),
        json=payload,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["changed"] is True
    assert cancelled.json()["booking"]["status"] == "cancelled"

    repeated = client.put(
        "/api/v1/scheduling/bookings/cancel",
        headers=auth_headers(request_id="booking-cancel-repeat"),
        json=payload,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["changed"] is False

    slots = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-17", "service_name": "Маникюр"},
    )
    assert slots.status_code == 200, slots.text
    assert any(value.startswith("2026-07-17T11:00:00") for value in slots.json()["starts_at"])
