from __future__ import annotations

from collections.abc import Callable

from conftest import WEB_ORIGIN_HEADERS
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import AuditEvent, User
from app.web_auth_models import WebLoginChallenge, WebSession


def _start(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/web/api/auth/challenges",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert response.status_code == 201
    return response.json()


def _approve(
    client: TestClient,
    auth_headers: Callable[..., dict[str, str]],
    code: str,
    telegram_user_id: int = 100000001,
):
    return client.post(
        "/api/v1/web-auth/challenges/approve",
        headers=auth_headers(telegram_user_id),
        json={"confirmation_code": code},
    )


def _csrf_headers(started: dict[str, object]) -> dict[str, str]:
    return {
        **WEB_ORIGIN_HEADERS,
        "X-CSRF-Token": str(started["csrf_token"]),
    }


def _consume(client: TestClient, started: dict[str, object]):
    return client.post(
        "/web/api/auth/challenges/consume",
        headers=_csrf_headers(started),
        json={"challenge_id": started["challenge_id"]},
    )


def test_web_login_happy_path_and_logout(client, create_user, auth_headers):
    create_user()
    started = _start(client)

    approval = _approve(
        client,
        auth_headers,
        str(started["confirmation_code"]),
    )
    assert approval.status_code == 200
    assert approval.json() == {"approved": True}

    consumed = _consume(client, started)
    assert consumed.status_code == 200
    assert consumed.json() == {"authenticated": True, "status": "consumed"}
    session_cookie = client.cookies.get("__Host-nails_session")
    assert session_cookie
    assert session_cookie != client.cookies.get("__Host-nails_login")

    state = client.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    assert state.status_code == 200
    assert state.json() == {"authenticated": True}

    logout = client.post(
        "/web/api/auth/logout",
        headers=_csrf_headers(started),
    )
    assert logout.status_code == 200
    assert logout.json() == {"logged_out": True}

    denied = client.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    assert denied.status_code == 401


def test_challenge_is_one_time_and_bound_to_original_browser(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    assert _approve(
        client,
        auth_headers,
        str(started["confirmation_code"]),
    ).json() == {"approved": True}

    other = TestClient(client.app, base_url="https://testserver")
    other.cookies.set(
        "__Host-nails_csrf",
        str(started["csrf_token"]),
        secure=True,
    )
    wrong_browser = other.post(
        "/web/api/auth/challenges/consume",
        headers=_csrf_headers(started),
        json={"challenge_id": started["challenge_id"]},
    )
    assert wrong_browser.status_code == 200
    assert wrong_browser.json()["authenticated"] is False

    first = _consume(client, started)
    assert first.json()["authenticated"] is True
    second = _consume(client, started)
    assert second.json() == {"authenticated": False, "status": "consumed"}

    other.close()


def test_unknown_code_and_inactive_user_do_not_create_session(
    client,
    create_user,
    auth_headers,
):
    create_user(is_active=False)
    started = _start(client)

    unknown = _approve(client, auth_headers, "000000")
    assert unknown.status_code == 403

    consume = _consume(client, started)
    assert consume.json()["authenticated"] is False
    with get_session_factory()() as session:
        assert session.scalar(select(WebSession)) is None


def test_web_boundary_rejects_missing_origin_and_bad_host(
    client,
    clean_database,
):
    missing_origin = client.post("/web/api/auth/challenges")
    assert missing_origin.status_code == 403

    bad_host = client.post(
        "/web/api/auth/challenges",
        headers={"Origin": "https://evil.example", "Host": "evil.example"},
    )
    assert bad_host.status_code == 400


def test_start_rate_limit_is_postgres_backed(client, clean_database):
    for _ in range(5):
        response = client.post(
            "/web/api/auth/challenges",
            headers=WEB_ORIGIN_HEADERS,
        )
        assert response.status_code == 201
    limited = client.post(
        "/web/api/auth/challenges",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert limited.status_code == 429


def test_plaintext_code_and_tokens_are_not_persisted_or_audited(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    code = str(started["confirmation_code"])
    login_cookie = client.cookies.get("__Host-nails_login")
    assert login_cookie
    assert _approve(client, auth_headers, code).json() == {"approved": True}
    assert _consume(client, started).json()["authenticated"] is True
    session_cookie = client.cookies.get("__Host-nails_session")
    assert session_cookie

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        assert code not in challenge.code_hash
        assert login_cookie not in challenge.browser_token_hash
        web_session = session.scalar(select(WebSession))
        assert web_session is not None
        assert session_cookie not in web_session.token_hash
        audit = session.scalars(select(AuditEvent)).all()
        serialized = " ".join(str(item.safe_changes) for item in audit)
        assert code not in serialized
        assert login_cookie not in serialized
        assert session_cookie not in serialized


def test_deactivated_user_is_rejected_on_next_request(
    client,
    create_user,
    auth_headers,
):
    user = create_user()
    started = _start(client)
    assert _approve(
        client,
        auth_headers,
        str(started["confirmation_code"]),
    ).json() == {"approved": True}
    assert _consume(client, started).json()["authenticated"] is True

    with get_session_factory()() as session:
        stored = session.get(User, user.id)
        assert stored is not None
        stored.is_active = False
        session.commit()

    denied = client.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    assert denied.status_code == 401
