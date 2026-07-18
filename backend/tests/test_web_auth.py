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
    started: dict[str, object],
    telegram_user_id: int = 100000001,
    *,
    verification_number: str | None = None,
):
    return client.post(
        "/api/v1/web-auth/challenges/approve",
        headers=auth_headers(telegram_user_id),
        json={
            "challenge_id": started["challenge_id"],
            "verification_number": verification_number
            or str(started["verification_number"]),
        },
    )


def _consume(client: TestClient, started: dict[str, object]):
    return client.post(
        "/web/api/auth/challenges/consume",
        headers=WEB_ORIGIN_HEADERS,
        json={"challenge_id": started["challenge_id"]},
    )


def test_web_login_happy_path_and_logout(client, create_user, auth_headers):
    create_user()
    started = _start(client)

    approval = _approve(client, auth_headers, started)
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
        headers=WEB_ORIGIN_HEADERS,
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
    assert _approve(client, auth_headers, started).json() == {"approved": True}

    other = TestClient(client.app, base_url="https://testserver")
    wrong_browser = other.post(
        "/web/api/auth/challenges/consume",
        headers=WEB_ORIGIN_HEADERS,
        json={"challenge_id": started["challenge_id"]},
    )
    assert wrong_browser.status_code == 200
    assert wrong_browser.json()["authenticated"] is False

    first = _consume(client, started)
    assert first.json()["authenticated"] is True
    second = _consume(client, started)
    assert second.json() == {"authenticated": False, "status": "consumed"}

    other.close()


def test_wrong_number_and_inactive_user_do_not_create_session(
    client,
    create_user,
    auth_headers,
):
    user = create_user()
    started = _start(client)

    wrong = _approve(
        client,
        auth_headers,
        started,
        verification_number="000000",
    )
    assert wrong.status_code == 200
    assert wrong.json() == {"approved": False}

    with get_session_factory()() as session:
        stored = session.get(User, user.id)
        assert stored is not None
        stored.is_active = False
        session.commit()

    denied = _approve(client, auth_headers, started)
    assert denied.status_code == 200
    assert denied.json() == {"approved": False}

    consume = _consume(client, started)
    assert consume.json()["authenticated"] is False
    with get_session_factory()() as session:
        assert session.scalar(select(WebSession)) is None


def test_tap_approve_contract_rejects_legacy_code_payload(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    response = client.post(
        "/api/v1/web-auth/challenges/approve",
        headers=auth_headers(),
        json={"confirmation_code": started["verification_number"]},
    )
    assert response.status_code == 422


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


def test_status_polling_rate_limit_is_postgres_backed(client, clean_database):
    started = _start(client)
    path = f"/web/api/auth/challenges/{started['challenge_id']}"
    for _ in range(30):
        response = client.get(path, headers=WEB_ORIGIN_HEADERS)
        assert response.status_code == 200
    limited = client.get(path, headers=WEB_ORIGIN_HEADERS)
    assert limited.status_code == 429


def test_consume_rate_limit_is_postgres_backed(client, clean_database):
    started = _start(client)
    for _ in range(10):
        response = _consume(client, started)
        assert response.status_code == 200
    limited = _consume(client, started)
    assert limited.status_code == 429


def test_tap_approve_number_bruteforce_is_rate_limited(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    for value in range(10):
        response = _approve(
            client,
            auth_headers,
            started,
            verification_number=f"{value:06d}",
        )
        assert response.status_code == 200
        assert response.json() == {"approved": False}
    limited = _approve(
        client,
        auth_headers,
        started,
        verification_number="999999",
    )
    assert limited.status_code == 200
    assert limited.json() == {"approved": False}


def test_plaintext_number_and_tokens_are_not_persisted_or_audited(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    verification_number = str(started["verification_number"])
    login_cookie = client.cookies.get("__Host-nails_login")
    assert login_cookie
    assert _approve(client, auth_headers, started).json() == {"approved": True}
    assert _consume(client, started).json()["authenticated"] is True
    session_cookie = client.cookies.get("__Host-nails_session")
    assert session_cookie

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        assert verification_number not in challenge.code_hash
        assert login_cookie not in challenge.browser_token_hash
        web_session = session.scalar(select(WebSession))
        assert web_session is not None
        assert session_cookie not in web_session.token_hash
        audit = session.scalars(select(AuditEvent)).all()
        serialized = " ".join(str(item.safe_changes) for item in audit)
        assert verification_number not in serialized
        assert login_cookie not in serialized
        assert session_cookie not in serialized


def test_deactivated_user_is_rejected_on_next_request(
    client,
    create_user,
    auth_headers,
):
    user = create_user()
    started = _start(client)
    assert _approve(client, auth_headers, started).json() == {"approved": True}
    assert _consume(client, started).json()["authenticated"] is True

    with get_session_factory()() as session:
        stored = session.get(User, user.id)
        assert stored is not None
        stored.is_active = False
        session.commit()

    denied = client.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    assert denied.status_code == 401


def test_status_requires_original_browser_cookie(client, clean_database):
    created = client.post(
        "/web/api/auth/challenges",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert created.status_code == 201
    challenge_id = created.json()["challenge_id"]
    path = f"/web/api/auth/challenges/{challenge_id}"
    assert client.get(path, headers=WEB_ORIGIN_HEADERS).status_code == 200
    client.cookies.clear()
    assert client.get(path, headers=WEB_ORIGIN_HEADERS).status_code == 404


def test_status_reports_expiry_without_mutating_challenge(client, clean_database):
    from datetime import UTC, datetime, timedelta

    created = client.post(
        "/web/api/auth/challenges",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert created.status_code == 201
    challenge_id = created.json()["challenge_id"]
    with get_session_factory()() as session:
        challenge = session.get(WebLoginChallenge, challenge_id)
        assert challenge is not None
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    path = f"/web/api/auth/challenges/{challenge_id}"
    response = client.get(path, headers=WEB_ORIGIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "expired"

    with get_session_factory()() as session:
        challenge = session.get(WebLoginChallenge, challenge_id)
        assert challenge is not None
        assert challenge.status == "pending"


def test_only_one_pending_challenge_per_browser(client, clean_database):
    first = _start(client)
    second = _start(client)

    with get_session_factory()() as session:
        first_row = session.get(WebLoginChallenge, first["challenge_id"])
        second_row = session.get(WebLoginChallenge, second["challenge_id"])
        assert first_row is not None
        assert second_row is not None
        assert first_row.status == "denied"
        assert second_row.status == "pending"
        assert first_row.pending_scope_hash == second_row.pending_scope_hash
        pending = session.scalars(
            select(WebLoginChallenge).where(
                WebLoginChallenge.status == "pending"
            )
        ).all()
        assert len(pending) == 1


def test_web_approval_identity_failures_are_neutral(
    client,
    create_user,
    auth_headers,
):
    started = _start(client)
    unknown = _approve(
        client,
        auth_headers,
        started,
        telegram_user_id=999999999,
    )
    assert unknown.status_code == 200
    assert unknown.json() == {"approved": False}

    create_user(telegram_user_id=100000002, is_active=False)
    inactive = _approve(
        client,
        auth_headers,
        started,
        telegram_user_id=100000002,
    )
    assert inactive.status_code == 200
    assert inactive.json() == {"approved": False}


def test_invalid_session_response_clears_cookie(client, clean_database):
    client.cookies.set("__Host-nails_session", "invalid-token")
    response = client.get(
        "/web/api/auth/session",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert response.status_code == 401
    cookie_headers = response.headers.get_list("set-cookie")
    assert any(
        "__Host-nails_session=" in value and "Max-Age=0" in value
        for value in cookie_headers
    )
