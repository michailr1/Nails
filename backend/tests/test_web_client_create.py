from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from conftest import WEB_ORIGIN_HEADERS
from sqlalchemy import func, select

from app.config import get_settings
from app.db import get_session_factory
from app.models import Client
from app.services.web_auth import _keyed_hash
from app.web_auth_models import WebSession


def _authenticate(client, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    token = "client-create-session-" + str(user_id)
    settings = get_settings()
    with get_session_factory()() as session:
        session.add(
            WebSession(
                token_hash=_keyed_hash(
                    token,
                    purpose="session-token",
                    settings=settings,
                ),
                user_id=user_id,
                last_seen_at=now,
                idle_expires_at=now + timedelta(hours=1),
                absolute_expires_at=now + timedelta(days=1),
                rotation_counter=1,
                created_ip_hash="b" * 64,
                last_ip_hash="b" * 64,
                request_id="web-client-create-test",
            )
        )
        session.commit()
    client.cookies.set("__Host-nails_session", token)


def test_web_client_create_requires_origin_and_returns_web_card(client, create_user):
    owner = create_user(telegram_user_id=100000211)
    _authenticate(client, owner.id)
    body = {"public_name": "  Марина   Тестовая  ", "phone": "+7 900 000-00-00"}

    missing_origin = client.post("/web/api/clients", json=body)
    assert missing_origin.status_code == 403
    assert missing_origin.json()["detail"]["code"] == "origin_required"

    response = client.post(
        "/web/api/clients",
        headers=WEB_ORIGIN_HEADERS,
        json=body,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["created"] is True
    assert result["contact_added"] is False
    assert result["client"]["public_name"] == "Марина Тестовая"
    assert result["client"]["phone"] == "+7 900 000-00-00"
    assert result["client"]["profile_status"] == "active"
    assert result["client"]["client_id"]

    repeated = client.post(
        "/web/api/clients",
        headers=WEB_ORIGIN_HEADERS,
        json={"public_name": "Марина Тестовая", "phone": "+7 900 000-00-00"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False

    with get_session_factory()() as session:
        assert session.scalar(select(func.count()).select_from(Client)) == 1


def test_web_client_create_can_add_phone_to_existing_client(client, create_user):
    owner = create_user(telegram_user_id=100000212)
    _authenticate(client, owner.id)

    first = client.post(
        "/web/api/clients",
        headers=WEB_ORIGIN_HEADERS,
        json={"public_name": "Ольга", "phone": None},
    )
    second = client.post(
        "/web/api/clients",
        headers=WEB_ORIGIN_HEADERS,
        json={"public_name": "Ольга", "phone": "+7 911 111-11-11"},
    )

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert second.status_code == 200
    result = second.json()
    assert result["created"] is False
    assert result["contact_added"] is True
    assert result["client"]["phone"] == "+7 911 111-11-11"
