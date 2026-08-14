from __future__ import annotations

from datetime import date, time, timedelta

from conftest import TEST_CLIENT_INTERNAL_API_KEY, WEB_ORIGIN_HEADERS

from app.client_models import MasterPublicProfile
from app.db import get_session_factory
from app.services.client_binding import create_master_link_token


def _client_headers(telegram_user_id: int, binding_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": TEST_CLIENT_INTERNAL_API_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
        "X-Request-ID": "calendar-day-off-321",
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = binding_id
    return headers


def _login_master(client, auth_headers, telegram_user_id: int) -> None:
    started = client.post(
        "/web/api/auth/challenges",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert started.status_code == 201
    challenge = started.json()
    approved = client.post(
        "/api/v1/web-auth/challenges/approve",
        headers=auth_headers(telegram_user_id),
        json={
            "challenge_id": challenge["challenge_id"],
            "verification_number": str(challenge["verification_number"]),
        },
    )
    assert approved.status_code == 200
    assert approved.json() == {"approved": True}
    consumed = client.post(
        "/web/api/auth/challenges/consume",
        headers=WEB_ORIGIN_HEADERS,
        json={"challenge_id": challenge["challenge_id"]},
    )
    assert consumed.status_code == 200
    assert consumed.json()["authenticated"] is True


def _start_binding(client, master_id, telegram_user_id: int) -> str:
    with get_session_factory()() as session:
        session.add(MasterPublicProfile(owner_user_id=master_id, display_name="Мастер"))
        token = create_master_link_token(session, owner_user_id=master_id).token
        session.commit()
    response = client.post(
        "/api/v1/client/start",
        headers=_client_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": "Анна"},
    )
    assert response.status_code == 200
    return response.json()["master"]["binding_id"]


def test_321_master_marks_day_off_in_web_and_client_slots_disappear(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master_telegram_id = 850000321
    client_telegram_id = 950000321
    master = create_user(telegram_user_id=master_telegram_id)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_after_minutes=0,
    )
    day = date.today() + timedelta(days=30)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(18))
    binding_id = _start_binding(client, master.id, client_telegram_id)

    draft_response = client.post(
        "/api/v1/client/booking-drafts",
        headers=_client_headers(client_telegram_id, binding_id),
        json={"service_name": "Маникюр"},
    )
    assert draft_response.status_code == 200
    draft_id = draft_response.json()["draft_id"]

    before = client.get(
        f"/api/v1/client/booking-drafts/{draft_id}/slots",
        headers=_client_headers(client_telegram_id),
        params={"day": day.isoformat()},
    )
    assert before.status_code == 200
    assert before.json()["starts_at"]

    _login_master(client, auth_headers, master_telegram_id)
    day_off = {
        "days": [
            {
                "day": day.isoformat(),
                "state": "unavailable",
                "intervals": [],
                "note": "Выходной",
            }
        ]
    }
    preview = client.post(
        "/web/api/schedule/preview",
        headers=WEB_ORIGIN_HEADERS,
        json=day_off,
    )
    assert preview.status_code == 200
    assert preview.json()["days"][0]["can_apply"] is True

    saved = client.put(
        "/web/api/schedule",
        headers=WEB_ORIGIN_HEADERS,
        json=day_off,
    )
    assert saved.status_code == 200

    after = client.get(
        f"/api/v1/client/booking-drafts/{draft_id}/slots",
        headers=_client_headers(client_telegram_id),
        params={"day": day.isoformat()},
    )
    assert after.status_code == 200
    assert after.json()["starts_at"] == []
    assert after.json()["is_working"] is False
