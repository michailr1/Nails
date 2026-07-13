from collections.abc import Callable
from datetime import date, time

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("clean_database")
def test_services_and_client_lookup_are_owner_scoped(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    first = create_user(telegram_user_id=100000001)
    second = create_user(telegram_user_id=100000002)
    create_service(first.id, public_name="Маникюр")
    create_service(second.id, public_name="Педикюр")

    first_services = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(telegram_user_id=100000001),
    )
    assert first_services.status_code == 200, first_services.text
    assert [item["public_name"] for item in first_services.json()["services"]] == [
        "Маникюр"
    ]

    missing = client.get(
        "/api/v1/scheduling/clients/exact",
        headers=auth_headers(telegram_user_id=100000001),
        params={"public_name": "Анна"},
    )
    assert missing.status_code == 200, missing.text
    assert missing.json() == {"found": False, "client": None}

    created = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(
            telegram_user_id=100000001,
            request_id="create-client-first",
        ),
        json={"public_name": "  Анна  ", "phone": None},
    )
    assert created.status_code == 200, created.text
    assert created.json()["created"] is True
    assert created.json()["client"]["public_name"] == "Анна"

    exact = client.get(
        "/api/v1/scheduling/clients/exact",
        headers=auth_headers(telegram_user_id=100000001),
        params={"public_name": "  АННА "},
    )
    assert exact.status_code == 200, exact.text
    assert exact.json()["found"] is True
    assert exact.json()["client"]["public_name"] == "Анна"

    isolated = client.get(
        "/api/v1/scheduling/clients/exact",
        headers=auth_headers(telegram_user_id=100000002),
        params={"public_name": "Анна"},
    )
    assert isolated.status_code == 200, isolated.text
    assert isolated.json()["found"] is False


@pytest.mark.usefixtures("clean_database")
def test_free_slots_use_service_duration_buffers_and_trusted_weekday(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(
        user.id,
        duration_minutes=120,
        buffer_before_minutes=0,
        buffer_after_minutes=21,
    )
    create_availability(
        user.id,
        day=date(2026, 7, 18),
        start_time=time(11, 0),
        end_time=time(20, 0),
    )

    response = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-18", "service_name": "маникюр"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["day"] == "2026-07-18"
    assert body["weekday_iso"] == 6
    assert body["timezone"] == "Europe/Berlin"
    assert body["availability_known"] is True
    assert body["is_working"] is True
    assert body["step_minutes"] == 15
    assert body["starts_at"][0] == "2026-07-18T11:00:00+02:00"
    assert body["starts_at"][-1] == "2026-07-18T17:30:00+02:00"
    assert len(body["starts_at"]) == 27


@pytest.mark.usefixtures("clean_database")
def test_unknown_and_unavailable_days_never_become_free(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id)

    unknown = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-17", "service_name": "Маникюр"},
    )
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["availability_known"] is False
    assert unknown.json()["is_working"] is False
    assert unknown.json()["starts_at"] == []

    create_availability(
        user.id,
        day=date(2026, 7, 18),
        start_time=None,
        end_time=None,
        is_available=False,
        note="не работаю",
    )
    unavailable = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": "2026-07-18", "service_name": "Маникюр"},
    )
    assert unavailable.status_code == 200, unavailable.text
    assert unavailable.json()["availability_known"] is True
    assert unavailable.json()["is_working"] is False
    assert unavailable.json()["starts_at"] == []
