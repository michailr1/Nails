from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("clean_database")
def test_no_show_can_be_corrected_to_completed_without_losing_fixed_snapshot(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    create_service(owner.id, price_amount="2700.00")

    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id="correction-client"),
        json={"public_name": "Анна Тестовая", "phone": None},
    )
    assert created_client.status_code == 200, created_client.text

    starts_at = "2026-07-17T11:00:00+02:00"
    created_booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="correction-booking"),
        json={
            "client_public_name": "Анна Тестовая",
            "service_name": "Маникюр",
            "starts_at": starts_at,
            "idempotency_key": "correction-fixed-booking",
        },
    )
    assert created_booking.status_code == 200, created_booking.text

    selector = {
        "client_public_name": "Анна Тестовая",
        "service_name": "Маникюр",
        "starts_at": starts_at,
    }
    no_show = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="correction-no-show"),
        json={**selector, "outcome": "no_show", "price_amount": None},
    )
    assert no_show.status_code == 200, no_show.text
    no_show_booking = no_show.json()["booking"]
    assert no_show_booking["status"] == "no_show"
    assert no_show_booking["price_amount"] is None
    assert no_show_booking["price_source"] == "final_no_show"
    assert no_show_booking["price_confirmed"] is False

    corrected = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="correction-completed"),
        json={**selector, "outcome": "completed", "price_amount": None},
    )
    assert corrected.status_code == 200, corrected.text
    corrected_booking = corrected.json()["booking"]
    assert corrected.json()["changed"] is True
    assert corrected_booking["status"] == "completed"
    assert corrected_booking["price_amount"] == "2700.00"
    assert corrected_booking["price_source"] == "catalog_fixed"
    assert corrected_booking["price_confirmed"] is True
