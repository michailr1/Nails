from collections.abc import Callable
from datetime import date, time

import pytest
from fastapi.testclient import TestClient


def _create_catalog_service(
    client: TestClient,
    auth_headers: Callable,
    *,
    public_name: str,
    price_type: str,
    price_amount: str | None = None,
    price_min_amount: str | None = None,
    price_max_amount: str | None = None,
) -> None:
    response = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="catalog-service-create"),
        json={
            "public_name": public_name,
            "public_description": None,
            "price_amount": price_amount,
            "currency": "RUB",
            "duration_minutes": 120,
            "buffer_before_minutes": 0,
            "buffer_after_minutes": 0,
            "is_active": True,
            "kind": "base",
            "price_type": price_type,
            "price_min_amount": price_min_amount,
            "price_max_amount": price_max_amount,
            "price_unit": None,
            "category": None,
            "sort_order": 0,
            "extra_minutes": 0,
        },
    )
    assert response.status_code == 200, response.text


def _create_booking(
    client: TestClient,
    auth_headers: Callable,
    *,
    client_name: str = "Анна Тестовая",
    service_name: str = "Маникюр",
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
            "service_name": service_name,
            "starts_at": starts_at,
            "idempotency_key": f"booking-{client_name}-{service_name}-{starts_at}",
        },
    )
    assert booking.status_code == 200, booking.text
    return booking.json()["booking"]


def _finalize_payload(
    *,
    client_name: str = "Анна Тестовая",
    service_name: str = "Маникюр",
    starts_at: str = "2026-07-17T11:00:00+02:00",
    outcome: str = "completed",
    price_amount: str | None = None,
) -> dict:
    return {
        "client_public_name": client_name,
        "service_name": service_name,
        "starts_at": starts_at,
        "outcome": outcome,
        "price_amount": price_amount,
    }


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
    assert any(
        value.startswith("2026-07-17T11:00:00")
        for value in slots.json()["starts_at"]
    )


@pytest.mark.usefixtures("clean_database")
def test_fixed_booking_finalize_preserves_snapshot_and_is_idempotent(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id, price_amount="2700.00")
    _create_booking(client, auth_headers)
    payload = _finalize_payload()

    finalized = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="booking-finalize"),
        json=payload,
    )
    assert finalized.status_code == 200, finalized.text
    result = finalized.json()
    assert result["changed"] is True
    assert result["booking"]["status"] == "completed"
    assert result["booking"]["price_amount"] == "2700.00"
    assert result["booking"]["price_confirmed"] is True
    assert result["booking"]["price_source"] == "catalog_fixed"

    repeated = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="booking-finalize-repeat"),
        json=payload,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["changed"] is False


@pytest.mark.usefixtures("clean_database")
def test_range_finalize_uses_lower_bound_without_claiming_confirmation(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    _create_catalog_service(
        client,
        auth_headers,
        public_name="Педикюр",
        price_type="range",
        price_min_amount="1900.00",
        price_max_amount="2100.00",
    )
    _create_booking(client, auth_headers, service_name="Педикюр")

    finalized = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="range-finalize"),
        json=_finalize_payload(service_name="Педикюр"),
    )
    assert finalized.status_code == 200, finalized.text
    booking = finalized.json()["booking"]
    assert booking["status"] == "completed"
    assert booking["price_amount"] == "1900.00"
    assert booking["price_source"] == "final_range_lower_bound_unconfirmed"
    assert booking["price_confirmed"] is False
    assert booking["price_min_amount"] == "1900.00"
    assert booking["price_max_amount"] == "2100.00"


@pytest.mark.usefixtures("clean_database")
def test_on_request_finalize_keeps_final_price_unknown_instead_of_zero(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    _create_catalog_service(
        client,
        auth_headers,
        public_name="Сложный дизайн",
        price_type="on_request",
    )
    _create_booking(client, auth_headers, service_name="Сложный дизайн")

    finalized = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="on-request-finalize"),
        json=_finalize_payload(service_name="Сложный дизайн"),
    )
    assert finalized.status_code == 200, finalized.text
    booking = finalized.json()["booking"]
    assert booking["status"] == "completed"
    assert booking["price_amount"] is None
    assert booking["price_source"] == "final_price_unknown"
    assert booking["price_confirmed"] is False


@pytest.mark.usefixtures("clean_database")
def test_finalize_allows_explicit_price_and_late_correction(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id, price_amount="2200.00")
    _create_booking(client, auth_headers)

    first = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="final-price-first"),
        json=_finalize_payload(price_amount="2400.00"),
    )
    assert first.status_code == 200, first.text
    assert first.json()["booking"]["price_amount"] == "2400.00"
    assert first.json()["booking"]["price_source"] == "final_manual_override"
    assert first.json()["booking"]["price_confirmed"] is True

    corrected = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="final-price-correction"),
        json=_finalize_payload(price_amount="2500.00"),
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["changed"] is True
    assert corrected.json()["booking"]["price_amount"] == "2500.00"
    assert corrected.json()["booking"]["price_source"] == "final_manual_override"


@pytest.mark.usefixtures("clean_database")
def test_no_show_is_soft_idempotent_and_never_presents_a_price(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id, price_amount="2700.00")
    _create_booking(client, auth_headers)
    payload = _finalize_payload(outcome="no_show")

    first = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="no-show-first"),
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert first.json()["booking"]["status"] == "no_show"
    assert first.json()["booking"]["price_amount"] is None
    assert first.json()["booking"]["price_source"] == "final_no_show"

    repeated = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="no-show-repeat"),
        json=payload,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["changed"] is False


@pytest.mark.usefixtures("clean_database")
def test_finalize_is_owner_scoped(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user(telegram_user_id=1001)
    create_user(telegram_user_id=2002)
    create_service(owner.id, price_amount="2700.00")
    _create_booking(
        client,
        lambda **kwargs: auth_headers(telegram_user_id=1001, **kwargs),
    )

    response = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(
            telegram_user_id=2002,
            request_id="cross-owner-finalize",
        ),
        json=_finalize_payload(),
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "booking_not_found"


@pytest.mark.usefixtures("clean_database")
def test_cancelled_booking_cannot_be_finalized(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id, price_amount="2700.00")
    _create_booking(client, auth_headers)
    selector = {
        "client_public_name": "Анна Тестовая",
        "service_name": "Маникюр",
        "starts_at": "2026-07-17T11:00:00+02:00",
    }
    cancelled = client.put(
        "/api/v1/scheduling/bookings/cancel",
        headers=auth_headers(request_id="cancel-before-finalize"),
        json=selector,
    )
    assert cancelled.status_code == 200, cancelled.text

    finalized = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="finalize-cancelled"),
        json={**selector, "outcome": "completed", "price_amount": None},
    )
    assert finalized.status_code == 409, finalized.text
    assert finalized.json()["detail"]["code"] == "booking_cancelled"


@pytest.mark.usefixtures("clean_database")
def test_future_booking_cannot_be_finalized(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id, price_amount="2700.00")
    starts_at = "2099-07-17T11:00:00+02:00"
    _create_booking(client, auth_headers, starts_at=starts_at)

    response = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(request_id="future-finalize"),
        json=_finalize_payload(starts_at=starts_at),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "booking_not_finished"


def test_no_show_payload_rejects_price(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    response = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=auth_headers(),
        json=_finalize_payload(outcome="no_show", price_amount="100.00"),
    )
    assert response.status_code == 422, response.text
