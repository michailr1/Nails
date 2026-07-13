from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import clear_runtime_caches, get_session_factory
from app.main import app
from app.models import AuditEvent


@pytest.mark.usefixtures("clean_database")
def test_preferences_start_empty_and_become_complete(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()

    empty = client.get("/api/v1/onboarding/preferences", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {
        "preferred_name": None,
        "assistant_style": None,
        "assistant_style_details": None,
        "is_complete": False,
    }

    named = client.put(
        "/api/v1/onboarding/preferences/name",
        headers=headers,
        json={"preferred_name": "  Настя   "},
    )
    assert named.status_code == 200
    assert named.json()["preferred_name"] == "Настя"
    assert named.json()["is_complete"] is False

    styled = client.put(
        "/api/v1/onboarding/preferences/style",
        headers=headers,
        json={
            "style": "friendly",
            "details": " тепло, но без лишних эмодзи ",
        },
    )
    assert styled.status_code == 200
    assert styled.json() == {
        "preferred_name": "Настя",
        "assistant_style": "friendly",
        "assistant_style_details": "тепло, но без лишних эмодзи",
        "is_complete": True,
    }


@pytest.mark.usefixtures("clean_database")
def test_custom_style_requires_description(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()

    response = client.put(
        "/api/v1/onboarding/preferences/style",
        headers=auth_headers(),
        json={"style": "custom"},
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("clean_database")
def test_preferences_are_isolated_between_two_users(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user(telegram_user_id=100000001)
    create_user(telegram_user_id=100000002)

    first_headers = auth_headers(telegram_user_id=100000001)
    second_headers = auth_headers(telegram_user_id=100000002)

    client.put(
        "/api/v1/onboarding/preferences/name",
        headers=first_headers,
        json={"preferred_name": "Настя"},
    )
    client.put(
        "/api/v1/onboarding/preferences/style",
        headers=first_headers,
        json={"style": "playful"},
    )

    second = client.get("/api/v1/onboarding/preferences", headers=second_headers)
    assert second.status_code == 200
    assert second.json() == {
        "preferred_name": None,
        "assistant_style": None,
        "assistant_style_details": None,
        "is_complete": False,
    }


@pytest.mark.usefixtures("clean_database")
def test_preferences_survive_new_application_session(
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()

    with TestClient(app) as first_client:
        first_client.put(
            "/api/v1/onboarding/preferences/name",
            headers=headers,
            json={"preferred_name": "Настя"},
        )
        first_client.put(
            "/api/v1/onboarding/preferences/style",
            headers=headers,
            json={"style": "casual", "details": "без официоза"},
        )

    clear_runtime_caches()

    with TestClient(app) as second_client:
        restored = second_client.get("/api/v1/onboarding/preferences", headers=headers)
        assert restored.status_code == 200
        assert restored.json()["preferred_name"] == "Настя"
        assert restored.json()["assistant_style"] == "casual"
        assert restored.json()["assistant_style_details"] == "без официоза"
        assert restored.json()["is_complete"] is True


@pytest.mark.usefixtures("clean_database")
def test_audit_does_not_store_name_or_free_text_style_details(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers(request_id="preferences-test")

    client.put(
        "/api/v1/onboarding/preferences/name",
        headers=headers,
        json={"preferred_name": "Секретное имя"},
    )
    client.put(
        "/api/v1/onboarding/preferences/style",
        headers=headers,
        json={"style": "custom", "details": "Очень личное описание"},
    )

    with get_session_factory()() as session:
        events = session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.owner_user_id == user.id,
                AuditEvent.object_type == "master_preferences",
            )
            .order_by(AuditEvent.created_at)
        ).all()

    assert [event.action for event in events] == [
        "master_preferences.name_saved",
        "master_preferences.style_saved",
    ]
    serialized = str([event.safe_changes for event in events])
    assert "Секретное имя" not in serialized
    assert "Очень личное описание" not in serialized
    assert events[0].safe_changes == {"preferred_name_set": True}
    assert events[1].safe_changes == {
        "assistant_style": "custom",
        "details_set": True,
    }
