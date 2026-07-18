from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import WEB_ORIGIN_HEADERS
from sqlalchemy import select

from app.db import get_session_factory
from app.web_auth_models import WebLoginChallenge


def _start(client):
    response = client.post("/web/api/auth/challenges", headers=WEB_ORIGIN_HEADERS)
    assert response.status_code == 201
    return response.json()


def _read(client, auth_headers, number, telegram_user_id=100000001):
    return client.get(
        "/api/v1/web-auth/conversation/challenge",
        headers=auth_headers(telegram_user_id),
        params={"verification_number": number},
    )


def _decide(client, auth_headers, number, decision, telegram_user_id=100000001):
    return client.post(
        "/api/v1/web-auth/conversation/decision",
        headers=auth_headers(telegram_user_id),
        json={"verification_number": number, "decision": decision},
    )


def test_master_can_claim_read_and_approve_own_challenge(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    number = str(started["verification_number"])

    read = _read(client, auth_headers, number)
    assert read.status_code == 200
    assert read.json()["status"] == "pending"
    assert read.json()["remaining_seconds"] > 0

    approved = _decide(client, auth_headers, number, "approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    consumed = client.post(
        "/web/api/auth/challenges/consume",
        headers=WEB_ORIGIN_HEADERS,
        json={"challenge_id": started["challenge_id"]},
    )
    assert consumed.json() == {"authenticated": True, "status": "consumed"}


def test_other_master_cannot_read_or_decide_claimed_challenge(
    client,
    create_user,
    auth_headers,
):
    create_user(100000001)
    create_user(100000002)
    started = _start(client)
    number = str(started["verification_number"])

    assert _read(client, auth_headers, number, 100000001).json()["status"] == "pending"
    assert _read(client, auth_headers, number, 100000002).json()["status"] == "not_found"
    assert _decide(client, auth_headers, number, "approve", 100000002).json()["status"] == "not_found"


def test_expired_challenge_cannot_be_approved(client, create_user, auth_headers):
    create_user()
    started = _start(client)
    number = str(started["verification_number"])

    with get_session_factory()() as session:
        challenge = session.scalar(select(WebLoginChallenge))
        assert challenge is not None
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    assert _read(client, auth_headers, number).json()["status"] == "not_found"
    assert _decide(client, auth_headers, number, "approve").json()["status"] == "not_found"


def test_repeated_approve_is_idempotent(client, create_user, auth_headers):
    create_user()
    started = _start(client)
    number = str(started["verification_number"])

    assert _read(client, auth_headers, number).json()["status"] == "pending"
    assert _decide(client, auth_headers, number, "approve").json()["status"] == "approved"
    assert _decide(client, auth_headers, number, "approve").json()["status"] == "approved"


def test_deny_is_idempotent_and_invalid_number_is_not_found(
    client,
    create_user,
    auth_headers,
):
    create_user()
    started = _start(client)
    number = str(started["verification_number"])

    assert _read(client, auth_headers, "000000").json()["status"] == "not_found"
    assert _read(client, auth_headers, number).json()["status"] == "pending"
    assert _decide(client, auth_headers, number, "deny").json()["status"] == "denied"
    assert _decide(client, auth_headers, number, "deny").json()["status"] == "denied"
