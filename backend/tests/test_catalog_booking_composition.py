from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


def _create_client(
    client: TestClient,
    headers: dict[str, str],
    public_name: str = "Анна",
) -> None:
    response = client.post(
        "/api/v1/scheduling/clients",
        headers=headers,
        json={"public_name": public_name},
    )
    assert response.status_code == 200, response.text


def _create_service(
    client: TestClient,
    headers: dict[str, str],
    payload: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        "/api/v1/scheduling/services",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()["service"]


def _create_booking(
    client: TestClient,
    headers: dict[str, str],
    *,
    idempotency_key: str,
    addon_names: list[str] | None = None,
    price_override_amount: str | None = None,
    duration_override_minutes: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "addon_names": addon_names or [],
        "starts_at": "2026-07-21T12:00:00+02:00",
        "idempotency_key": idempotency_key,
    }
    if price_override_amount is not None:
        payload["price_override_amount"] = price_override_amount
    if duration_override_minutes is not None:
        payload["duration_override_minutes"] = duration_override_minutes

    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.usefixtures("clean_database")
def test_range_composition_preserves_estimate_until_manual_override(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers(request_id="range-composition")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        {
            "public_name": "Маникюр",
            "price_type": "range",
            "price_min_amount": "2500.00",
            "price_max_amount": "3000.00",
            "duration_minutes": 120,
        },
    )
    _create_service(
        client,
        headers,
        {
            "public_name": "Ремонт",
            "kind": "addon",
            "price_amount": "300.00",
            "extra_minutes": 15,
        },
    )

    response = _create_booking(
        client,
        headers,
        idempotency_key="range-with-addon",
        addon_names=["Ремонт"],
    )
    booking = response["booking"]

    assert booking["price_type"] == "range"
    assert booking["price_amount"] is None
    assert booking["price_min_amount"] == "2800.00"
    assert booking["price_max_amount"] == "3300.00"
    assert booking["price_source"] == "catalog_range"
    assert booking["price_confirmed"] is False
    assert booking["duration_minutes"] == 135
    assert booking["duration_source"] == "catalog_v2"


@pytest.mark.usefixtures("clean_database")
def test_manual_overrides_win_without_erasing_catalog_semantics(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers(request_id="manual-overrides")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        {
            "public_name": "Маникюр",
            "price_type": "range",
            "price_min_amount": "2500.00",
            "price_max_amount": "3000.00",
            "duration_minutes": 120,
        },
    )
    _create_service(
        client,
        headers,
        {
            "public_name": "Ремонт",
            "kind": "addon",
            "price_amount": "300.00",
            "extra_minutes": 15,
        },
    )

    response = _create_booking(
        client,
        headers,
        idempotency_key="manual-overrides",
        addon_names=["Ремонт"],
        price_override_amount="3100.00",
        duration_override_minutes=150,
    )
    booking = response["booking"]

    assert booking["price_type"] == "range"
    assert booking["price_min_amount"] == "2800.00"
    assert booking["price_max_amount"] == "3300.00"
    assert booking["price_amount"] == "3100.00"
    assert booking["price_source"] == "manual_override"
    assert booking["price_confirmed"] is True
    assert booking["duration_minutes"] == 150
    assert booking["duration_source"] == "manual_override"


@pytest.mark.usefixtures("clean_database")
def test_on_request_never_appears_as_confirmed_zero(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers(request_id="on-request-booking")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        {
            "public_name": "Маникюр",
            "price_type": "on_request",
            "duration_minutes": 120,
        },
    )

    response = _create_booking(
        client,
        headers,
        idempotency_key="on-request-booking",
    )
    booking = response["booking"]

    assert booking["price_type"] == "on_request"
    assert booking["price_amount"] is None
    assert booking["price_min_amount"] is None
    assert booking["price_max_amount"] is None
    assert booking["price_source"] == "catalog_on_request"
    assert booking["price_confirmed"] is False


@pytest.mark.usefixtures("clean_database")
def test_idempotency_includes_addons_and_overrides(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers(request_id="idempotency-composition")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        {
            "public_name": "Маникюр",
            "price_amount": "2700.00",
            "duration_minutes": 120,
        },
    )
    _create_service(
        client,
        headers,
        {
            "public_name": "Снятие",
            "kind": "addon",
            "price_amount": "500.00",
            "extra_minutes": 20,
        },
    )

    first = _create_booking(
        client,
        headers,
        idempotency_key="same-key",
        addon_names=["Снятие"],
        price_override_amount="3000.00",
    )
    repeated = _create_booking(
        client,
        headers,
        idempotency_key="same-key",
        addon_names=["Снятие"],
        price_override_amount="3000.00",
    )
    assert first["created"] is True
    assert repeated["created"] is False
    assert repeated["booking"]["id"] == first["booking"]["id"]

    conflict = client.post(
        "/api/v1/scheduling/bookings",
        headers=headers,
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "addon_names": [],
            "starts_at": "2026-07-21T12:00:00+02:00",
            "price_override_amount": "3000.00",
            "idempotency_key": "same-key",
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"


@pytest.mark.usefixtures("clean_database")
def test_catalog_changes_do_not_rewrite_booking_snapshot(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers(request_id="snapshot-immutability")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        {
            "public_name": "Маникюр",
            "price_amount": "2700.00",
            "duration_minutes": 120,
        },
    )
    _create_service(
        client,
        headers,
        {
            "public_name": "Снятие",
            "kind": "addon",
            "price_amount": "500.00",
            "extra_minutes": 20,
        },
    )
    created = _create_booking(
        client,
        headers,
        idempotency_key="snapshot-immutability",
        addon_names=["Снятие"],
    )["booking"]

    replaced = client.put(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="addon-update"),
        json={
            "current_public_name": "Снятие",
            "public_name": "Снятие",
            "kind": "addon",
            "price_amount": "900.00",
            "currency": "RUB",
            "duration_minutes": None,
            "extra_minutes": 45,
            "buffer_before_minutes": 0,
            "buffer_after_minutes": 0,
        },
    )
    assert replaced.status_code == 200, replaced.text

    day = client.get(
        "/api/v1/scheduling/day",
        headers=headers,
        params={"day": "2026-07-21"},
    )
    assert day.status_code == 200, day.text
    booking = day.json()["bookings"][0]

    assert booking["id"] == created["id"]
    assert booking["price_amount"] == "3200.00"
    assert booking["duration_minutes"] == 140
    addon_item = next(
        item for item in booking["catalog_items"] if item["kind"] == "addon"
    )
    assert addon_item["price_amount"] == "500.00"
    assert addon_item["extra_minutes"] == 20


@pytest.mark.usefixtures("clean_database")
def test_addons_are_owner_scoped(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user(telegram_user_id=100000001)
    create_user(telegram_user_id=100000002)
    owner_headers = auth_headers(100000001, request_id="owner-booking")
    other_headers = auth_headers(100000002, request_id="other-addon")

    _create_client(client, owner_headers)
    _create_service(
        client,
        owner_headers,
        {
            "public_name": "Маникюр",
            "price_amount": "2700.00",
            "duration_minutes": 120,
        },
    )
    _create_service(
        client,
        other_headers,
        {
            "public_name": "Снятие",
            "kind": "addon",
            "price_amount": "500.00",
            "extra_minutes": 20,
        },
    )

    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=owner_headers,
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "addon_names": ["Снятие"],
            "starts_at": "2026-07-21T12:00:00+02:00",
            "idempotency_key": "owner-scoped-addon",
        },
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "addon_not_found"
