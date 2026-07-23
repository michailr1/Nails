from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("clean_database")
def test_addon_is_created_but_cannot_be_used_as_primary_service(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()

    addon = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="addon-create"),
        json={
            "public_name": "Снятие",
            "kind": "addon",
            "price_type": "fixed",
            "price_amount": "500.00",
            "extra_minutes": 20,
        },
    )
    assert addon.status_code == 200, addon.text
    assert addon.json()["service"]["kind"] == "addon"
    assert addon.json()["service"]["duration_minutes"] is None
    assert addon.json()["service"]["extra_minutes"] == 20

    slots = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-20", "service_name": "Снятие"},
    )
    assert slots.status_code == 404, slots.text
    assert slots.json()["detail"]["code"] == "service_not_found"

    booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="addon-primary-booking"),
        json={
            "client_public_name": "Анна",
            "service_name": "Снятие",
            "starts_at": "2026-07-20T12:00:00+02:00",
            "idempotency_key": "addon-primary-booking",
        },
    )
    assert booking.status_code == 404, booking.text
    assert booking.json()["detail"]["code"] == "service_not_found"


@pytest.mark.usefixtures("clean_database")
def test_fixed_addon_extends_price_and_duration_snapshot(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id="client-create"),
        json={"public_name": "Анна"},
    )
    assert created_client.status_code == 200, created_client.text

    base = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="base-create"),
        json={
            "public_name": "Маникюр",
            "price_amount": "2700.00",
            "duration_minutes": 120,
            "buffer_after_minutes": 20,
        },
    )
    assert base.status_code == 200, base.text

    addon = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="addon-create"),
        json={
            "public_name": "Снятие",
            "kind": "addon",
            "price_amount": "500.00",
            "extra_minutes": 20,
        },
    )
    assert addon.status_code == 200, addon.text

    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="composed-booking"),
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "addon_names": ["Снятие"],
            "starts_at": "2026-07-20T12:00:00+02:00",
            "idempotency_key": "composed-booking",
        },
    )
    assert response.status_code == 200, response.text

    booking = response.json()["booking"]
    assert booking["service_name"] == "Маникюр"
    assert booking["addon_names"] == ["Снятие"]
    assert [item["kind"] for item in booking["catalog_items"]] == ["base", "addon"]
    assert booking["price_type"] == "fixed"
    assert booking["price_amount"] == "3200.00"
    assert booking["price_min_amount"] == "3200.00"
    assert booking["price_max_amount"] == "3200.00"
    assert booking["price_source"] == "catalog_fixed"
    assert booking["price_confirmed"] is True
    assert booking["duration_minutes"] == 140
    assert booking["duration_source"] == "catalog_v3"
    assert booking["buffer_after_minutes"] == 20
