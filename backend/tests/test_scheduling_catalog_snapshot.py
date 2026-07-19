from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("clean_database")
def test_catalog_replace_preserves_existing_booking_snapshot(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    create_service(
        owner.id,
        public_name="Маникюр",
        price_amount="2500.00",
        duration_minutes=120,
    )
    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id="catalog-snapshot-client"),
        json={"public_name": "Анна", "phone": None},
    )
    assert created_client.status_code == 200, created_client.text
    created_booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="catalog-snapshot-booking"),
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "starts_at": "2026-07-17T11:00:00+03:00",
            "idempotency_key": "catalog-snapshot-booking",
        },
    )
    assert created_booking.status_code == 200, created_booking.text
    before = created_booking.json()["booking"]

    replaced = client.put(
        "/api/v1/scheduling/services/catalog",
        headers=auth_headers(request_id="catalog-snapshot-replace"),
        json={
            "services": [
                {
                    "public_name": "Маникюр",
                    "public_description": None,
                    "price_amount": "3200.00",
                    "currency": "RUB",
                    "duration_minutes": 150,
                    "buffer_before_minutes": 0,
                    "buffer_after_minutes": 0,
                    "is_active": True,
                    "kind": "base",
                    "price_type": "fixed",
                    "price_min_amount": None,
                    "price_max_amount": None,
                    "price_unit": None,
                    "category": None,
                    "sort_order": 0,
                    "extra_minutes": 0,
                }
            ]
        },
    )
    assert replaced.status_code == 200, replaced.text

    day = client.get(
        "/api/v1/scheduling/day",
        headers=auth_headers(request_id="catalog-snapshot-readback"),
        params={"day": "2026-07-17"},
    )
    assert day.status_code == 200, day.text
    existing = day.json()["bookings"][0]
    assert existing["price_amount"] == before["price_amount"] == "2500.00"
    assert existing["duration_minutes"] == before["duration_minutes"] == 120
