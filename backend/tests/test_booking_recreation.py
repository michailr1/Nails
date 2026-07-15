from collections.abc import Callable
from datetime import date, time

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("clean_database")
def test_exact_booking_can_be_recreated_and_managed_after_cancellation(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(
        user.id,
        price_amount="2700.00",
        duration_minutes=120,
        buffer_after_minutes=21,
    )
    create_availability(
        user.id,
        day=date(2026, 7, 17),
        start_time=time(11),
        end_time=time(18),
    )
    assert client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id="client-create"),
        json={"public_name": "Анна Тестовая", "phone": None},
    ).status_code == 200

    selector = {
        "client_public_name": "Анна Тестовая",
        "service_name": "Маникюр",
        "starts_at": "2026-07-17T11:00:00+02:00",
    }
    original_response = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="booking-original"),
        json={**selector, "idempotency_key": "booking-original-lifecycle"},
    )
    assert original_response.status_code == 200, original_response.text
    original = original_response.json()["booking"]

    first_cancel = client.put(
        "/api/v1/scheduling/bookings/cancel",
        headers=auth_headers(request_id="booking-first-cancel"),
        json=selector,
    )
    assert first_cancel.status_code == 200, first_cancel.text
    assert first_cancel.json()["changed"] is True

    recreated_response = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="booking-recreate"),
        json={**selector, "idempotency_key": "booking-recreated-lifecycle"},
    )
    assert recreated_response.status_code == 200, recreated_response.text
    recreated = recreated_response.json()
    assert recreated["created"] is True
    assert recreated["booking"]["status"] == "scheduled"
    assert recreated["booking"]["id"] != original["id"]

    day = client.get(
        "/api/v1/scheduling/day",
        headers=auth_headers(),
        params={"day": "2026-07-17"},
    )
    assert day.status_code == 200, day.text
    assert [booking["id"] for booking in day.json()["bookings"]] == [
        recreated["booking"]["id"]
    ]

    second_cancel = client.put(
        "/api/v1/scheduling/bookings/cancel",
        headers=auth_headers(request_id="booking-second-cancel"),
        json=selector,
    )
    assert second_cancel.status_code == 200, second_cancel.text
    assert second_cancel.json()["changed"] is True
    assert second_cancel.json()["booking"]["id"] == recreated["booking"]["id"]

    repeated_cancel = client.put(
        "/api/v1/scheduling/bookings/cancel",
        headers=auth_headers(request_id="booking-second-cancel-repeat"),
        json=selector,
    )
    assert repeated_cancel.status_code == 200, repeated_cancel.text
    assert repeated_cancel.json()["changed"] is False
    assert repeated_cancel.json()["booking"]["id"] == recreated["booking"]["id"]
