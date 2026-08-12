from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import WEB_ORIGIN_HEADERS
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.web_auth_models import WebChallengeStatus, WebLoginChallenge, WebSession


def _start(client: TestClient) -> dict[str, object]:
    response = client.post("/web/api/auth/challenges", headers=WEB_ORIGIN_HEADERS)
    assert response.status_code == 201
    return response.json()


def _approve_conversation(client, auth_headers, number: str):
    return client.post(
        "/api/v1/web-auth/conversation/decision",
        headers=auth_headers(),
        json={"verification_number": number, "decision": "approve"},
    )


def _continue(client: TestClient, token: str):
    return client.get(
        "/web/api/auth/continue",
        params={"token": token},
        follow_redirects=False,
    )


def test_approve_returns_one_time_continuation_that_logs_in_new_browser(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    approved = _approve_conversation(
        client,
        auth_headers,
        str(started["verification_number"]),
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    token = body["continuation_token"]
    assert isinstance(token, str)
    assert str(started["challenge_id"]) in token

    telegram_browser = TestClient(client.app, base_url="https://testserver")
    opened = _continue(telegram_browser, token)
    assert opened.status_code == 303
    assert opened.headers["location"] == "/web/"
    assert opened.headers["cache-control"] == "no-store"
    assert "referrer-policy" not in opened.headers
    assert telegram_browser.cookies.get("__Host-nails_session")
    state = telegram_browser.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    assert state.status_code == 200
    assert state.json() == {"authenticated": True}

    replay = TestClient(client.app, base_url="https://testserver")
    repeated = _continue(replay, token)
    assert repeated.status_code == 303
    assert replay.cookies.get("__Host-nails_session") is None
    denied = replay.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    assert denied.status_code == 401

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        assert challenge.status == WebChallengeStatus.continued.value

    telegram_browser.close()
    replay.close()


def test_continuation_still_works_if_original_browser_consumed_first(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    approved = _approve_conversation(
        client,
        auth_headers,
        str(started["verification_number"]),
    ).json()
    token = approved["continuation_token"]

    original = client.post(
        "/web/api/auth/challenges/consume",
        headers=WEB_ORIGIN_HEADERS,
        json={"challenge_id": started["challenge_id"]},
    )
    assert original.json() == {"authenticated": True, "status": "consumed"}

    telegram_browser = TestClient(client.app, base_url="https://testserver")
    opened = _continue(telegram_browser, token)
    assert opened.status_code == 303
    assert telegram_browser.cookies.get("__Host-nails_session")

    with get_session_factory()() as session:
        sessions = session.scalars(select(WebSession)).all()
        assert len(sessions) == 2
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        assert challenge.status == WebChallengeStatus.continued.value

    telegram_browser.close()


def test_tampered_or_expired_continuation_does_not_authenticate(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    approved = _approve_conversation(
        client,
        auth_headers,
        str(started["verification_number"]),
    ).json()
    token = approved["continuation_token"]

    tampered = TestClient(client.app, base_url="https://testserver")
    bad_token = f"{token[:-1]}{'0' if token[-1] != '0' else '1'}"
    response = _continue(tampered, bad_token)
    assert response.status_code == 303
    assert tampered.cookies.get("__Host-nails_session") is None

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    expired = TestClient(client.app, base_url="https://testserver")
    response = _continue(expired, token)
    assert response.status_code == 303
    assert expired.cookies.get("__Host-nails_session") is None

    with get_session_factory()() as session:
        assert session.scalar(select(WebSession)) is None

    tampered.close()
    expired.close()


def test_read_and_deny_never_return_continuation_token(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    number = str(started["verification_number"])

    read = client.get(
        "/api/v1/web-auth/conversation/challenge",
        headers=auth_headers(),
        params={"verification_number": number},
    )
    assert read.status_code == 200
    assert "continuation_token" not in read.json()

    denied = client.post(
        "/api/v1/web-auth/conversation/decision",
        headers=auth_headers(),
        json={"verification_number": number, "decision": "deny"},
    )
    assert denied.status_code == 200
    assert denied.json()["status"] == "denied"
    assert "continuation_token" not in denied.json()
