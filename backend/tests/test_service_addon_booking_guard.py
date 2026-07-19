from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("clean_database")
def test_addon_write_is_blocked_until_legacy_rollback_window_closes(
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
    assert addon.status_code == 409, addon.text
    assert addon.json()["detail"]["code"] == "addon_rollout_not_enabled"

    catalog = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(),
    )
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["services"] == []

    slots = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-20", "service_name": "Снятие"},
    )
    assert slots.status_code == 404, slots.text
    assert slots.json()["detail"]["code"] == "service_not_found"

    booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="addon-booking"),
        json={
            "client_public_name": "Анна",
            "service_name": "Снятие",
            "starts_at": "2026-07-20T12:00:00+03:00",
            "idempotency_key": "addon-booking",
        },
    )
    assert booking.status_code == 404, booking.text
    assert booking.json()["detail"]["code"] == "service_not_found"
