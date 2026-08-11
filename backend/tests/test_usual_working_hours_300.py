from __future__ import annotations

from datetime import date, timedelta

from app.client_models import MasterPublicProfile
from app.db import get_session_factory
from app.services.client_binding import create_master_link_token

CLIENT_KEY = "c" * 64


def _client_headers(telegram_user_id: int, binding_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
        "X-Request-ID": "usual-working-hours-300",
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = binding_id
    return headers


def _start_binding(client, master, telegram_user_id: int) -> str:
    with get_session_factory()() as session:
        session.add(MasterPublicProfile(owner_user_id=master.id, display_name="Мастер"))
        session.flush()
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()
    response = client.post(
        "/api/v1/client/start",
        headers=_client_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": "Клиентка"},
    )
    assert response.status_code == 200, response.text
    return response.json()["master"]["binding_id"]


def _client_draft(client, binding_id: str, telegram_user_id: int) -> str:
    response = client.post(
        "/api/v1/client/booking-drafts",
        headers=_client_headers(telegram_user_id, binding_id),
        json={"service_name": "Маникюр"},
    )
    assert response.status_code == 200, response.text
    return response.json()["draft_id"]


def _client_slot_hours(client, draft_id: str, telegram_user_id: int, day: date) -> list[str]:
    response = client.get(
        f"/api/v1/client/booking-drafts/{draft_id}/slots",
        headers=_client_headers(telegram_user_id),
        params={"day": day.isoformat()},
    )
    assert response.status_code == 200, response.text
    return [value[11:16] for value in response.json()["starts_at"]]


def test_usual_hours_saved_once_bound_client_slot_suggestions(
    client,
    create_user,
    create_service,
    auth_headers,
):
    master = create_user(telegram_user_id=880000001)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    headers = auth_headers(master.telegram_user_id, request_id="usual-hours-save-300")

    saved = client.put(
        "/api/v1/onboarding/preferences/default-work-hours",
        headers=headers,
        json={"intervals": [{"start_time": "10:00", "end_time": "21:00"}]},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["default_work_intervals"] == [
        {"start_time": "10:00:00", "end_time": "21:00:00"}
    ]

    telegram_user_id = 980000001
    binding_id = _start_binding(client, master, telegram_user_id)
    draft_id = _client_draft(client, binding_id, telegram_user_id)
    hours = _client_slot_hours(
        client,
        draft_id,
        telegram_user_id,
        date.today() + timedelta(days=21),
    )

    assert hours
    assert hours[0] == "10:00"
    assert hours[-1] == "20:00"
    assert all("10:00" <= value <= "20:00" for value in hours)


def test_date_exception_overrides_usual_hours_for_client_slots(
    client,
    create_user,
    create_service,
    auth_headers,
):
    master = create_user(telegram_user_id=880000002)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    headers = auth_headers(master.telegram_user_id, request_id="usual-hours-override-300")
    day = date.today() + timedelta(days=22)

    saved = client.put(
        "/api/v1/onboarding/preferences/default-work-hours",
        headers=headers,
        json={"intervals": [{"start_time": "10:00", "end_time": "21:00"}]},
    )
    assert saved.status_code == 200, saved.text
    overridden = client.put(
        "/api/v1/scheduling/availability",
        headers=headers,
        json={
            "days": [
                {
                    "day": day.isoformat(),
                    "state": "available",
                    "intervals": [{"start_time": "12:00", "end_time": "18:00"}],
                    "note": None,
                }
            ]
        },
    )
    assert overridden.status_code == 200, overridden.text

    telegram_user_id = 980000002
    binding_id = _start_binding(client, master, telegram_user_id)
    draft_id = _client_draft(client, binding_id, telegram_user_id)
    hours = _client_slot_hours(client, draft_id, telegram_user_id, day)

    assert hours[0] == "12:00"
    assert hours[-1] == "17:00"


def test_client_slots_keep_adr006_fallback_without_saved_hours(
    client,
    create_user,
    create_service,
):
    master = create_user(telegram_user_id=880000003)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )

    telegram_user_id = 980000003
    binding_id = _start_binding(client, master, telegram_user_id)
    draft_id = _client_draft(client, binding_id, telegram_user_id)
    hours = _client_slot_hours(
        client,
        draft_id,
        telegram_user_id,
        date.today() + timedelta(days=23),
    )

    assert hours[0] == "10:00"
    assert hours[-1] == "22:00"
