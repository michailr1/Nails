from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

NON_FIXED_PAYLOADS = [
    pytest.param(
        {
            "price_type": "range",
            "price_min_amount": "1900.00",
            "price_max_amount": "2300.00",
        },
        id="range",
    ),
    pytest.param(
        {
            "price_type": "per_unit",
            "price_amount": "100.00",
            "price_unit": "1 ноготь",
        },
        id="per-unit",
    ),
    pytest.param(
        {"price_type": "on_request"},
        id="on-request",
    ),
]


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize("price_fields", NON_FIXED_PAYLOADS)
def test_non_fixed_create_leaves_no_legacy_visible_service(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    price_fields: dict[str, object],
) -> None:
    create_user()

    response = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id=f"create-{price_fields['price_type']}"),
        json={
            "public_name": "Небезопасная цена",
            "duration_minutes": 120,
            **price_fields,
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "price_type_rollout_not_enabled"

    catalog = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(),
    )
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["services"] == []

    slots = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-20", "service_name": "Небезопасная цена"},
    )
    assert slots.status_code == 404, slots.text
    assert slots.json()["detail"]["code"] == "service_not_found"

    booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id=f"booking-{price_fields['price_type']}"),
        json={
            "client_public_name": "Анна",
            "service_name": "Небезопасная цена",
            "starts_at": "2026-07-20T12:00:00+03:00",
            "idempotency_key": f"booking-{price_fields['price_type']}",
        },
    )
    assert booking.status_code == 404, booking.text
    assert booking.json()["detail"]["code"] == "service_not_found"


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize("price_fields", NON_FIXED_PAYLOADS)
def test_non_fixed_replace_cannot_change_legacy_fixed_price(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    price_fields: dict[str, object],
) -> None:
    create_user()

    created = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="fixed-create"),
        json={
            "public_name": "Маникюр",
            "price_amount": "2700.00",
            "duration_minutes": 120,
        },
    )
    assert created.status_code == 200, created.text

    replaced = client.put(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id=f"replace-{price_fields['price_type']}"),
        json={
            "current_public_name": "Маникюр",
            "public_name": "Маникюр",
            "currency": "RUB",
            "duration_minutes": 120,
            "buffer_before_minutes": 0,
            "buffer_after_minutes": 0,
            **price_fields,
        },
    )
    assert replaced.status_code == 409, replaced.text
    assert replaced.json()["detail"]["code"] == "price_type_rollout_not_enabled"

    lookup = client.get(
        "/api/v1/scheduling/services/exact",
        headers=auth_headers(),
        params={"public_name": "Маникюр"},
    )
    assert lookup.status_code == 200, lookup.text
    service = lookup.json()["service"]
    assert service["kind"] == "base"
    assert service["price_type"] == "fixed"
    assert service["price_amount"] == "2700.00"
