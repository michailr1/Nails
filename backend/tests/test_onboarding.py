from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import clear_runtime_caches, get_session_factory
from app.main import app
from app.models import AuditEvent, UserRole


def full_schedule(opening: str = "09:00:00", closing: str = "18:00:00") -> dict:
    return {
        "days": [
            {
                "weekday": weekday,
                "is_working": weekday < 5,
                "start_time": opening if weekday < 5 else None,
                "end_time": closing if weekday < 5 else None,
            }
            for weekday in range(7)
        ]
    }


def services_payload() -> dict:
    return {
        "services": [
            {
                "public_name": "Маникюр",
                "public_description": "Тестовая услуга",
                "price_amount": "50.00",
                "currency": "EUR",
                "duration_minutes": 90,
            }
        ]
    }


def buffers_payload() -> dict:
    return {
        "buffers": [
            {
                "service_name": "Маникюр",
                "before_minutes": 10,
                "after_minutes": 15,
            }
        ]
    }


def bookings_payload() -> dict:
    return {
        "bookings": [
            {
                "client_public_name": "Тестовый клиент A",
                "client_phone": "+70000000001",
                "service_name": "Маникюр",
                "starts_at": "2026-08-01T10:00:00+02:00",
            }
        ]
    }


def section(response: dict, name: str) -> dict:
    return next(item for item in response["sections"] if item["section"] == name)


def start(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post("/api/v1/onboarding/start", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def save(
    client: TestClient,
    headers: dict[str, str],
    name: str,
    payload: dict,
) -> dict:
    response = client.put(
        f"/api/v1/onboarding/sections/{name}",
        headers=headers,
        json={"payload": payload},
    )
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client: TestClient, headers: dict[str, str], name: str) -> dict:
    response = client.post(
        f"/api/v1/onboarding/sections/{name}/confirm",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def complete_all_sections(
    client: TestClient,
    headers: dict[str, str],
) -> dict:
    save(client, headers, "schedule", full_schedule())
    confirm(client, headers, "schedule")
    save(client, headers, "services", services_payload())
    confirm(client, headers, "services")
    save(client, headers, "buffers", buffers_payload())
    confirm(client, headers, "buffers")
    save(client, headers, "bookings", bookings_payload())
    return confirm(client, headers, "bookings")


@pytest.mark.usefixtures("clean_database")
def test_requests_require_internal_key_and_known_active_user(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()

    missing_key = client.post(
        "/api/v1/onboarding/start",
        headers={"X-Telegram-User-ID": "100000001"},
    )
    assert missing_key.status_code == 401
    assert missing_key.json()["detail"]["code"] == "unauthorized"

    wrong_key = client.post(
        "/api/v1/onboarding/start",
        headers=auth_headers(internal_key="x" * 40),
    )
    assert wrong_key.status_code == 401

    unknown_user = client.post(
        "/api/v1/onboarding/start",
        headers=auth_headers(telegram_user_id=100000999),
    )
    assert unknown_user.status_code == 403

    create_user(telegram_user_id=100000002, is_active=False)
    inactive_user = client.post(
        "/api/v1/onboarding/start",
        headers=auth_headers(telegram_user_id=100000002),
    )
    assert inactive_user.status_code == 403


@pytest.mark.parametrize("role", [UserRole.master, UserRole.admin])
@pytest.mark.usefixtures("clean_database")
def test_master_and_admin_can_start_onboarding(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    role: UserRole,
) -> None:
    create_user(role=role)
    body = start(client, auth_headers())
    assert body["status"] == "in_progress"
    assert body["current_step"] == "schedule"
    assert body["sections"] == []


@pytest.mark.usefixtures("clean_database")
def test_pause_resume_and_state_survive_new_application_session(
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()

    with TestClient(app) as first_client:
        start(first_client, headers)
        save(
            first_client,
            headers,
            "schedule",
            {
                "days": [
                    {
                        "weekday": 0,
                        "is_working": True,
                        "start_time": "09:00",
                        "end_time": "18:00",
                    }
                ]
            },
        )
        paused = first_client.post("/api/v1/onboarding/pause", headers=headers)
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

    clear_runtime_caches()

    with TestClient(app) as second_client:
        restored = second_client.get("/api/v1/onboarding", headers=headers)
        assert restored.status_code == 200
        body = restored.json()
        assert body["status"] == "paused"
        assert section(body, "schedule")["draft_payload"]["days"][0]["weekday"] == 0

        resumed = second_client.post("/api/v1/onboarding/resume", headers=headers)
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "in_progress"


@pytest.mark.usefixtures("clean_database")
def test_confirmation_is_idempotent_and_correction_preserves_last_confirmed_payload(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers()
    start(client, headers)
    save(client, headers, "schedule", full_schedule())

    first = confirm(client, headers, "schedule")
    second = confirm(client, headers, "schedule")
    assert first == second

    confirmed = section(first, "schedule")
    assert confirmed["revision"] == 1
    assert confirmed["confirmed_revision"] == 1
    assert confirmed["is_current_revision_confirmed"] is True
    assert confirmed["effective_payload"] == confirmed["draft_payload"]

    corrected_state = save(
        client,
        headers,
        "schedule",
        full_schedule(opening="10:00:00", closing="19:00:00"),
    )
    corrected = section(corrected_state, "schedule")
    assert corrected["revision"] == 2
    assert corrected["confirmed_revision"] == 1
    assert corrected["is_current_revision_confirmed"] is False
    assert corrected["effective_payload"] == confirmed["effective_payload"]
    assert corrected["draft_payload"] != corrected["effective_payload"]

    with get_session_factory()() as session:
        confirmation_count = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "onboarding.section_confirmed",
            )
        )
    assert confirmation_count == 1


@pytest.mark.usefixtures("clean_database")
def test_unconfirmed_draft_is_not_effective(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()
    start(client, headers)
    body = save(client, headers, "schedule", full_schedule())
    schedule = section(body, "schedule")
    assert schedule["draft_payload"]
    assert schedule["effective_payload"] is None
    assert schedule["confirmed_payload"] is None


@pytest.mark.usefixtures("clean_database")
def test_confirmation_order_and_service_references_are_enforced(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()
    start(client, headers)

    save(client, headers, "services", services_payload())
    out_of_order = client.post(
        "/api/v1/onboarding/sections/services/confirm",
        headers=headers,
    )
    assert out_of_order.status_code == 409
    assert out_of_order.json()["detail"]["code"] == "prior_sections_not_confirmed"

    save(client, headers, "schedule", full_schedule())
    confirm(client, headers, "schedule")
    confirm(client, headers, "services")

    save(
        client,
        headers,
        "buffers",
        {
            "buffers": [
                {
                    "service_name": "Неизвестная услуга",
                    "before_minutes": 5,
                    "after_minutes": 5,
                }
            ]
        },
    )
    unknown = client.post(
        "/api/v1/onboarding/sections/buffers/confirm",
        headers=headers,
    )
    assert unknown.status_code == 409
    assert unknown.json()["detail"]["code"] == "unknown_service_reference"


@pytest.mark.usefixtures("clean_database")
def test_reconfirming_upstream_section_invalidates_downstream_confirmations(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()
    start(client, headers)
    complete_all_sections(client, headers)

    save(
        client,
        headers,
        "services",
        {
            "services": [
                {
                    "public_name": "Маникюр",
                    "price_amount": "55.00",
                    "currency": "EUR",
                    "duration_minutes": 100,
                }
            ]
        },
    )
    body = confirm(client, headers, "services")

    assert body["current_step"] == "buffers"
    assert section(body, "services")["is_current_revision_confirmed"] is True
    for downstream in ("buffers", "bookings"):
        value = section(body, downstream)
        assert value["is_current_revision_confirmed"] is False
        assert value["effective_payload"] is None


@pytest.mark.usefixtures("clean_database")
def test_complete_requires_all_current_revisions_and_is_idempotent(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers(request_id="complete-test")
    start(client, headers)

    incomplete = client.post("/api/v1/onboarding/complete", headers=headers)
    assert incomplete.status_code == 409
    assert incomplete.json()["detail"]["code"] == "onboarding_sections_not_confirmed"

    complete_all_sections(client, headers)
    first = client.post("/api/v1/onboarding/complete", headers=headers)
    second = client.post("/api/v1/onboarding/complete", headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "completed"
    assert first.json()["current_step"] is None
    assert second.status_code == 200
    assert second.json() == first.json()

    with get_session_factory()() as session:
        completion_count = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.action == "onboarding.completed",
            )
        )
    assert completion_count == 1


@pytest.mark.usefixtures("clean_database")
def test_invalid_payload_is_rejected_without_audit_payload_leak(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers()
    start(client, headers)

    response = client.put(
        "/api/v1/onboarding/sections/schedule",
        headers=headers,
        json={
            "payload": {
                "days": [
                    {
                        "weekday": 0,
                        "is_working": True,
                        "start_time": "18:00",
                        "end_time": "09:00",
                    }
                ]
            }
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_onboarding_payload"

    with get_session_factory()() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.owner_user_id == user.id)
        ).all()
    assert all("payload" not in event.safe_changes for event in events)


@pytest.mark.usefixtures("clean_database")
def test_schedule_confirmation_requires_all_weekdays(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()
    start(client, headers)
    save(
        client,
        headers,
        "schedule",
        {"days": [{"weekday": 0, "is_working": False}]},
    )
    response = client.post(
        "/api/v1/onboarding/sections/schedule/confirm",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "schedule_requires_all_weekdays"
