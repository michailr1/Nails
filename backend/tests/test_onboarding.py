from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import clear_runtime_caches, get_session_factory
from app.main import app
from app.models import AuditEvent, UserRole


def services_payload(duration_minutes: int = 90) -> dict:
    return {
        "services": [
            {
                "public_name": "Маникюр",
                "public_description": "Базовая услуга",
                "price_amount": "50.00",
                "currency": "EUR",
                "duration_minutes": duration_minutes,
            }
        ]
    }


def buffers_payload(service_name: str = "Маникюр") -> dict:
    return {
        "buffers": [
            {
                "service_name": service_name,
                "before_minutes": 10,
                "after_minutes": 15,
            }
        ]
    }


def availability_payload() -> dict:
    return {
        "days": [
            {
                "day": "2026-07-15",
                "is_available": True,
                "intervals": [
                    {"start_time": "10:00", "end_time": "14:00"},
                    {"start_time": "16:00", "end_time": "20:00"},
                ],
                "note": "принимаю по записи",
            },
            {
                "day": "2026-07-16",
                "is_available": False,
                "intervals": [],
                "note": "не работаю",
            },
        ]
    }


def bookings_payload() -> dict:
    return {
        "bookings": [
            {
                "client_public_name": "Анна",
                "client_phone": "+491234567890",
                "service_name": "Маникюр",
                "starts_at": "2026-07-15T10:00:00+02:00",
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


def complete_all_sections(client: TestClient, headers: dict[str, str]) -> dict:
    save(client, headers, "services", services_payload())
    confirm(client, headers, "services")
    save(client, headers, "buffers", buffers_payload())
    confirm(client, headers, "buffers")
    save(client, headers, "availability", availability_payload())
    confirm(client, headers, "availability")
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
def test_master_and_admin_start_with_services_not_weekly_schedule(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    role: UserRole,
) -> None:
    create_user(role=role)
    body = start(client, auth_headers())

    assert body["status"] == "in_progress"
    assert body["current_step"] == "services"
    assert body["sections"] == []


@pytest.mark.usefixtures("clean_database")
def test_pause_resume_and_service_draft_survive_new_application_session(
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()

    with TestClient(app) as first_client:
        start(first_client, headers)
        save(first_client, headers, "services", services_payload())
        paused = first_client.post("/api/v1/onboarding/pause", headers=headers)
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

    clear_runtime_caches()

    with TestClient(app) as second_client:
        restored = second_client.get("/api/v1/onboarding", headers=headers)
        assert restored.status_code == 200
        body = restored.json()
        assert body["status"] == "paused"
        assert section(body, "services")["draft_payload"]["services"][0][
            "duration_minutes"
        ] == 90

        resumed = second_client.post("/api/v1/onboarding/resume", headers=headers)
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "in_progress"


@pytest.mark.usefixtures("clean_database")
def test_confirmation_is_idempotent_and_correction_preserves_last_confirmation(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers()
    start(client, headers)
    save(client, headers, "services", services_payload())

    first = confirm(client, headers, "services")
    second = confirm(client, headers, "services")
    assert first == second

    confirmed = section(first, "services")
    assert confirmed["revision"] == 1
    assert confirmed["confirmed_revision"] == 1
    assert confirmed["is_current_revision_confirmed"] is True

    corrected_state = save(client, headers, "services", services_payload(duration_minutes=120))
    corrected = section(corrected_state, "services")
    assert corrected["revision"] == 2
    assert corrected["confirmed_revision"] == 1
    assert corrected["is_current_revision_confirmed"] is False
    assert corrected["effective_payload"] == confirmed["effective_payload"]

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
def test_confirmation_order_and_service_references_are_enforced(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()
    start(client, headers)

    save(client, headers, "buffers", buffers_payload())
    out_of_order = client.post(
        "/api/v1/onboarding/sections/buffers/confirm",
        headers=headers,
    )
    assert out_of_order.status_code == 409
    assert out_of_order.json()["detail"]["code"] == "prior_sections_not_confirmed"

    save(client, headers, "services", services_payload())
    confirm(client, headers, "services")
    save(client, headers, "buffers", buffers_payload("Неизвестная услуга"))

    unknown = client.post(
        "/api/v1/onboarding/sections/buffers/confirm",
        headers=headers,
    )
    assert unknown.status_code == 409
    assert unknown.json()["detail"]["code"] == "unknown_service_reference"


@pytest.mark.usefixtures("clean_database")
def test_availability_supports_multiple_intervals_and_explicit_day_off(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()
    start(client, headers)
    save(client, headers, "services", services_payload())
    confirm(client, headers, "services")
    save(client, headers, "buffers", {"buffers": []})
    confirm(client, headers, "buffers")

    body = save(client, headers, "availability", availability_payload())
    availability = section(body, "availability")["draft_payload"]["days"]

    assert availability[0]["day"] == "2026-07-15"
    assert len(availability[0]["intervals"]) == 2
    assert availability[1]["day"] == "2026-07-16"
    assert availability[1]["is_available"] is False
    assert availability[1]["intervals"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {
            "days": [
                {
                    "day": "2026-07-15",
                    "is_available": True,
                    "intervals": [
                        {"start_time": "10:00", "end_time": "15:00"},
                        {"start_time": "14:00", "end_time": "18:00"},
                    ],
                }
            ]
        },
        {
            "days": [
                {
                    "day": "2026-07-15",
                    "is_available": False,
                    "intervals": [{"start_time": "10:00", "end_time": "12:00"}],
                }
            ]
        },
    ],
)
@pytest.mark.usefixtures("clean_database")
def test_invalid_date_availability_is_rejected(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    payload: dict,
) -> None:
    create_user()
    start(client, auth_headers())

    response = client.put(
        "/api/v1/onboarding/sections/availability",
        headers=auth_headers(),
        json={"payload": payload},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_onboarding_payload"


@pytest.mark.usefixtures("clean_database")
def test_reconfirming_services_invalidates_downstream_sections(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()
    start(client, headers)
    complete_all_sections(client, headers)

    save(client, headers, "services", services_payload(duration_minutes=120))
    body = confirm(client, headers, "services")

    assert body["current_step"] == "buffers"
    assert section(body, "services")["is_current_revision_confirmed"] is True
    for downstream in ("buffers", "availability", "bookings"):
        value = section(body, downstream)
        assert value["is_current_revision_confirmed"] is False
        assert value["effective_payload"] is None


@pytest.mark.usefixtures("clean_database")
def test_complete_requires_all_current_sections_and_is_idempotent(
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
def test_two_users_cannot_see_each_others_availability(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user(telegram_user_id=100000001)
    create_user(telegram_user_id=100000002)

    first_headers = auth_headers(telegram_user_id=100000001)
    second_headers = auth_headers(telegram_user_id=100000002)

    start(client, first_headers)
    save(client, first_headers, "availability", availability_payload())
    start(client, second_headers)

    second = client.get("/api/v1/onboarding", headers=second_headers)
    assert second.status_code == 200
    assert second.json()["sections"] == []

    first = client.get("/api/v1/onboarding", headers=first_headers)
    assert section(first.json(), "availability")["draft_payload"]["days"][0][
        "day"
    ] == "2026-07-15"


@pytest.mark.usefixtures("clean_database")
def test_invalid_payload_does_not_leak_business_values_into_audit(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers()
    start(client, headers)

    secret_note = "Секретная личная заметка"
    response = client.put(
        "/api/v1/onboarding/sections/availability",
        headers=headers,
        json={
            "payload": {
                "days": [
                    {
                        "day": "2026-07-15",
                        "is_available": True,
                        "intervals": [
                            {"start_time": "18:00", "end_time": "09:00"}
                        ],
                        "note": secret_note,
                    }
                ]
            }
        },
    )
    assert response.status_code == 422

    with get_session_factory()() as session:
        values = session.scalars(
            select(AuditEvent.safe_changes).where(AuditEvent.owner_user_id == user.id)
        ).all()

    assert secret_note not in str(values)
