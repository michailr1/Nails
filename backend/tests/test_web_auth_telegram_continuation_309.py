from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

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


def test_continuation_does_not_consume_original_browser_challenge(
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
    assert opened.headers["location"] == f"/web/#continue={quote(token, safe='')}"
    assert opened.headers["cache-control"] == "no-store"
    assert opened.headers["referrer-policy"] == "no-referrer"
    assert telegram_browser.cookies.get("__Host-nails_session")
    telegram_state = telegram_browser.get(
        "/web/api/auth/session", headers=WEB_ORIGIN_HEADERS
    )
    assert telegram_state.status_code == 200
    assert telegram_state.json() == {"authenticated": True}

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        assert challenge.status == WebChallengeStatus.approved.value

    original = client.post(
        "/web/api/auth/challenges/consume",
        headers=WEB_ORIGIN_HEADERS,
        json={"challenge_id": started["challenge_id"]},
    )
    assert original.status_code == 200
    assert original.json() == {"authenticated": True, "status": "consumed"}

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        assert challenge.status == WebChallengeStatus.consumed.value
        sessions = session.scalars(select(WebSession)).all()
        assert len(sessions) == 2

    telegram_browser.close()


def test_continuation_remains_reusable_within_ttl_after_browser_consume(
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

    first = TestClient(client.app, base_url="https://testserver")
    second = TestClient(client.app, base_url="https://testserver")
    first_open = _continue(first, token)
    second_open = _continue(second, token)
    assert first_open.status_code == 303
    assert second_open.status_code == 303
    assert first.cookies.get("__Host-nails_session")
    assert second.cookies.get("__Host-nails_session")

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        assert challenge.status == WebChallengeStatus.consumed.value
        sessions = session.scalars(select(WebSession)).all()
        assert len(sessions) == 3

    first.close()
    second.close()


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
    assert response.headers["location"] == "/web/"
    assert tampered.cookies.get("__Host-nails_session") is None

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    expired = TestClient(client.app, base_url="https://testserver")
    response = _continue(expired, token)
    assert response.status_code == 303
    assert response.headers["location"] == "/web/"
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


def test_frontend_auth_state_machine_fails_closed_and_exposes_browser_handoff():
    static_root = Path(__file__).resolve().parents[1] / "app" / "web_static"
    guard = (static_root / "web-auth-state-machine.js").read_text()
    index = (static_root / "index.html").read_text()

    assert 'new Set(["pending"])' in guard
    assert "WEB_AUTH_OPEN_STATUSES.has(current.status)" in guard
    assert "unknown" not in guard.lower() or "неизвестном состоянии" in guard
    assert 'textContent = "Открыть в браузере"' in guard
    assert 'new URLSearchParams(fragment).get("continue")' in guard
    assert "userAgent" not in guard
    assert "navigator.userAgent" not in guard
    assert 'src="/web/web-auth-state-machine.js"' in index


def test_public_web_proxy_hides_upstream_security_header_duplicates():
    nginx = (Path(__file__).resolve().parents[2] / "web" / "nginx.conf").read_text()
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
    ):
        assert f"proxy_hide_header {header};" in nginx
        assert f"add_header {header} " in nginx
