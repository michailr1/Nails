from collections.abc import Callable
from datetime import date, time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


SERVICE_PAYLOAD = {
    "public_name": "Маникюр",
    "public_description": "Покрытие и обработка",
    "price_amount": "2500.00",
    "currency": "RUB",
    "duration_minutes": 120,
    "buffer_before_minutes": 0,
    "buffer_after_minutes": 21,
    "is_active": True,
}


@pytest.mark.usefixtures("clean_database")
def test_services_can_be_created_and_repeated_safely_after_onboarding(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()

    created = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="service-create"),
        json=SERVICE_PAYLOAD,
    )
    assert created.status_code == 200, created.text
    assert created.json()["created"] is True
    assert created.json()["service"] == {
        **SERVICE_PAYLOAD,
        "price_amount": "2500.00",
        "id": created.json()["service"]["id"],
    }

    repeated = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="service-create-repeat"),
        json=SERVICE_PAYLOAD,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["created"] is False
    assert repeated.json()["service"]["id"] == created.json()["service"]["id"]

    conflict = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="service-create-conflict"),
        json={**SERVICE_PAYLOAD, "price_amount": "2700.00"},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "service_name_conflict"


@pytest.mark.usefixtures("clean_database")
def test_service_changes_apply_to_future_bookings_without_rewriting_existing_snapshots(
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
    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(),
        json={"public_name": "Анна", "phone": None},
    )
    assert created_client.status_code == 200, created_client.text

    booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="booking-before-service-change"),
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "starts_at": "2026-07-18T12:30:00+02:00",
            "idempotency_key": "booking-before-service-change",
        },
    )
    assert booking.status_code == 200, booking.text
    assert booking.json()["booking"]["price_amount"] == "2500.00"
    assert booking.json()["booking"]["duration_minutes"] == 120
    assert booking.json()["booking"]["buffer_after_minutes"] == 21

    updated = client.put(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="service-update"),
        json={
            "current_public_name": "Маникюр",
            "public_name": "Маникюр плюс",
            "public_description": "Обновлённое описание",
            "price_amount": "2700.00",
            "currency": "RUB",
            "duration_minutes": 135,
            "buffer_before_minutes": 10,
            "buffer_after_minutes": 15,
            "is_active": True,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["changed"] is True
    assert set(body["changed_fields"]) == {
        "public_name",
        "public_description",
        "price_amount",
        "duration_minutes",
        "buffer_before_minutes",
        "buffer_after_minutes",
    }
    assert body["service"]["public_name"] == "Маникюр плюс"
    assert body["service"]["price_amount"] == "2700.00"

    day_view = client.get(
        "/api/v1/scheduling/day",
        headers=auth_headers(),
        params={"day": "2026-07-18"},
    )
    assert day_view.status_code == 200, day_view.text
    existing = day_view.json()["bookings"][0]
    assert existing["service_name"] == "Маникюр плюс"
    assert existing["price_amount"] == "2500.00"
    assert existing["duration_minutes"] == 120
    assert existing["buffer_before_minutes"] == 0
    assert existing["buffer_after_minutes"] == 21

    old_name = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-18", "service_name": "Маникюр"},
    )
    assert old_name.status_code == 404, old_name.text

    new_name = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-18", "service_name": "Маникюр плюс"},
    )
    assert new_name.status_code == 200, new_name.text
    assert new_name.json()["service"]["duration_minutes"] == 135
    assert new_name.json()["service"]["buffer_before_minutes"] == 10
    assert new_name.json()["service"]["buffer_after_minutes"] == 15


@pytest.mark.usefixtures("clean_database")
def test_service_can_be_archived_and_restored_without_deleting_history(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id)

    archived = client.put(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="service-archive"),
        json={
            "current_public_name": "Маникюр",
            **SERVICE_PAYLOAD,
            "is_active": False,
        },
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["service"]["is_active"] is False
    assert archived.json()["changed_fields"] == ["is_active"]

    active_list = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(),
    )
    assert active_list.status_code == 200, active_list.text
    assert active_list.json()["services"] == []

    all_services = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(),
        params={"include_inactive": "true"},
    )
    assert all_services.status_code == 200, all_services.text
    assert len(all_services.json()["services"]) == 1
    assert all_services.json()["services"][0]["is_active"] is False

    lookup = client.get(
        "/api/v1/scheduling/services/exact",
        headers=auth_headers(),
        params={"public_name": "Маникюр"},
    )
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()["found"] is True
    assert lookup.json()["service"]["is_active"] is False

    restored = client.put(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="service-restore"),
        json={
            "current_public_name": "Маникюр",
            **SERVICE_PAYLOAD,
            "is_active": True,
        },
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["service"]["is_active"] is True


@pytest.mark.usefixtures("clean_database")
def test_service_rename_conflict_and_owner_isolation(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    first = create_user(telegram_user_id=100000001)
    second = create_user(telegram_user_id=100000002)
    create_service(first.id, public_name="Маникюр")
    create_service(first.id, public_name="Педикюр", price_amount=Decimal("2800.00"))
    create_service(second.id, public_name="Маникюр", price_amount=Decimal("999.00"))

    conflict = client.put(
        "/api/v1/scheduling/services",
        headers=auth_headers(telegram_user_id=100000001),
        json={
            "current_public_name": "Маникюр",
            "public_name": "Педикюр",
            "public_description": None,
            "price_amount": "2500.00",
            "currency": "RUB",
            "duration_minutes": 120,
            "buffer_before_minutes": 0,
            "buffer_after_minutes": 21,
            "is_active": True,
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "service_name_conflict"

    second_lookup = client.get(
        "/api/v1/scheduling/services/exact",
        headers=auth_headers(telegram_user_id=100000002),
        params={"public_name": "Маникюр"},
    )
    assert second_lookup.status_code == 200, second_lookup.text
    assert second_lookup.json()["service"]["price_amount"] == "999.00"
