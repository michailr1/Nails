from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import get_session_factory
from app.feedback_models import FeedbackEvent
from app.models import UserRole


def test_master_saves_masked_feedback_and_admin_can_read_delete(
    client,
    create_user,
    auth_headers,
):
    master = create_user(telegram_user_id=100000011)
    admin = create_user(telegram_user_id=100000012, role=UserRole.admin)

    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers(100000011),
        json={
            "kind": "thumbs_down",
            "context": [
                {"role": "user", "content": "Позвони +49 151 23456789, ответ не тот"},
                {
                    "role": "assistant",
                    "content": "email test@example.com token=super-secret /opt/nails/file",
                },
            ],
        },
    )
    assert response.status_code == 201
    event_id = response.json()["event_id"]

    forbidden = client.get(
        "/api/v1/feedback",
        headers=auth_headers(100000011),
    )
    assert forbidden.status_code == 403

    listed = client.get(
        "/api/v1/feedback",
        headers=auth_headers(100000012),
    )
    assert listed.status_code == 200
    events = listed.json()["events"]
    assert len(events) == 1
    assert events[0]["owner_user_id"] == str(master.id)
    assert events[0]["actor_user_id"] == str(master.id)
    text = " ".join(item["content"] for item in events[0]["safe_context"])
    assert "+49" not in text
    assert "test@example.com" not in text
    assert "super-secret" not in text
    assert "/opt/" not in text
    assert "[phone]" in text
    assert "[email]" in text
    assert "[secret]" in text
    assert "[technical]" in text

    deleted = client.delete(
        f"/api/v1/feedback/{event_id}",
        headers=auth_headers(100000012),
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}

    with get_session_factory()() as session:
        assert session.scalar(select(FeedbackEvent)) is None

    assert admin.role is UserRole.admin


def test_feedback_retention_is_applied_on_admin_read(
    client,
    create_user,
    auth_headers,
):
    master = create_user(telegram_user_id=100000021)
    create_user(telegram_user_id=100000022, role=UserRole.admin)

    with get_session_factory()() as session:
        session.add(
            FeedbackEvent(
                owner_user_id=master.id,
                actor_user_id=master.id,
                kind="unrecognized",
                safe_context=[{"role": "user", "content": "старый запрос"}],
                created_at=datetime.now(UTC) - timedelta(days=31),
            )
        )
        session.commit()

    listed = client.get(
        "/api/v1/feedback",
        headers=auth_headers(100000022),
    )
    assert listed.status_code == 200
    assert listed.json() == {"events": []}


def test_feedback_context_limits_are_server_enforced(
    client,
    create_user,
    auth_headers,
):
    create_user(telegram_user_id=100000031)
    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers(100000031),
        json={
            "kind": "thumbs_down",
            "context": [
                {"role": "user", "content": str(index)} for index in range(5)
            ],
        },
    )
    assert response.status_code == 422
