from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import get_session_factory
from app.feedback_models import FeedbackEvent, FeedbackKind
from app.models import AuditEvent, UserRole


def _payload() -> dict[str, object]:
    return {
        "kind": "thumbs_down",
        "context": [
            {
                "role": "assistant",
                "text": "Нет, завтра — 2026-07-17. 2026-07-18 будет послезавтра.",
            },
            {
                "role": "user",
                "text": "👎",
            },
        ],
    }


def test_feedback_preserves_exact_context_and_audit_omits_context(
    client,
    create_user,
    auth_headers,
):
    user = create_user()

    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers(),
        json=_payload(),
    )

    assert response.status_code == 200
    response_body = response.json()
    assert response_body["saved"] is True
    response_context = response_body["safe_context"]

    with get_session_factory()() as session:
        event = session.scalar(select(FeedbackEvent))
        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.action == "feedback.created")
        )

    assert event is not None
    assert event.owner_user_id == user.id
    assert event.actor_user_id == user.id
    assert event.kind == FeedbackKind.thumbs_down
    assert response_context == event.safe_context
    assert response_context == _payload()["context"]
    assert "2026-07-17" in response_context[0]["text"]
    assert "2026-07-18" in response_context[0]["text"]
    assert "<phone>" not in response_context[0]["text"]

    assert audit is not None
    assert audit.safe_changes == {"kind": "thumbs_down"}
    assert "context" not in audit.safe_changes


def test_feedback_read_and_delete_are_admin_only(
    client,
    create_user,
    auth_headers,
):
    create_user()
    admin = create_user(telegram_user_id=100000002, role=UserRole.admin)

    created = client.post(
        "/api/v1/feedback",
        headers=auth_headers(),
        json=_payload(),
    )
    feedback_id = created.json()["feedback_id"]

    denied = client.get("/api/v1/feedback", headers=auth_headers())
    assert denied.status_code == 403

    listed = client.get(
        "/api/v1/feedback",
        headers=auth_headers(telegram_user_id=admin.telegram_user_id),
    )
    assert listed.status_code == 200
    assert len(listed.json()["events"]) == 1

    deleted = client.delete(
        f"/api/v1/feedback/{feedback_id}",
        headers=auth_headers(telegram_user_id=admin.telegram_user_id),
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}

    with get_session_factory()() as session:
        assert session.scalar(select(FeedbackEvent)) is None
        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.action == "feedback.deleted")
        )

    assert audit is not None
    assert audit.actor_user_id == admin.id
    assert audit.safe_changes == {"kind": "thumbs_down"}


def test_feedback_access_purges_expired_events(
    client,
    create_user,
    auth_headers,
):
    user = create_user()

    with get_session_factory()() as session:
        session.add(
            FeedbackEvent(
                owner_user_id=user.id,
                actor_user_id=user.id,
                kind=FeedbackKind.unrecognized,
                safe_context=[{"role": "user", "text": "старое"}],
                created_at=datetime.now(UTC) - timedelta(days=31),
            )
        )
        session.commit()

    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers(),
        json=_payload(),
    )
    assert response.status_code == 200

    with get_session_factory()() as session:
        events = session.scalars(select(FeedbackEvent)).all()

    assert len(events) == 1
    assert events[0].kind == FeedbackKind.thumbs_down


def test_feedback_context_shape_is_bounded(
    client,
    create_user,
    auth_headers,
):
    create_user()
    payload = {
        "kind": "thumbs_down",
        "context": [
            {"role": "user", "text": str(index)} for index in range(5)
        ],
    }

    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers(),
        json=payload,
    )

    assert response.status_code == 422
