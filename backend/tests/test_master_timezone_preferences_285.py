from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.db import get_session_factory
from app.models import AuditEvent, User


@pytest.mark.usefixtures("clean_database")
def test_timezone_preference_falls_back_updates_and_isolates_owners(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    first = create_user(telegram_user_id=100000101)
    second = create_user(telegram_user_id=100000102)
    first_headers = auth_headers(
        telegram_user_id=100000101,
        request_id="timezone-preference-first",
    )
    second_headers = auth_headers(telegram_user_id=100000102)

    initial = client.get(
        "/api/v1/onboarding/preferences/timezone",
        headers=first_headers,
    )
    assert initial.status_code == 200
    assert initial.json() == {"timezone": "Europe/Berlin"}

    changed = client.put(
        "/api/v1/onboarding/preferences/timezone",
        headers=first_headers,
        json={"timezone": "Asia/Yekaterinburg"},
    )
    assert changed.status_code == 200
    assert changed.json() == {"timezone": "Asia/Yekaterinburg"}

    first_readback = client.get(
        "/api/v1/onboarding/preferences/timezone",
        headers=first_headers,
    )
    second_readback = client.get(
        "/api/v1/onboarding/preferences/timezone",
        headers=second_headers,
    )
    assert first_readback.json() == {"timezone": "Asia/Yekaterinburg"}
    assert second_readback.json() == {"timezone": "Europe/Berlin"}

    with get_session_factory()() as session:
        assert session.get(User, first.id).timezone == "Asia/Yekaterinburg"
        assert session.get(User, second.id).timezone is None
        audit = session.query(AuditEvent).filter_by(
            owner_user_id=first.id,
            action="master_preferences.timezone_saved",
        ).one()
        assert audit.safe_changes == {"timezone": "Asia/Yekaterinburg"}


@pytest.mark.usefixtures("clean_database")
def test_timezone_preference_rejects_unknown_iana_name(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()

    response = client.put(
        "/api/v1/onboarding/preferences/timezone",
        headers=auth_headers(),
        json={"timezone": "Mars/Olympus"},
    )

    assert response.status_code == 422
