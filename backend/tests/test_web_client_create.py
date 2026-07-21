from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from conftest import WEB_ORIGIN_HEADERS
from sqlalchemy import func, select

from app.config import get_settings
from app.db import get_session_factory
from app.models import Client, ClientProfileStatus
from app.services.normalization import normalize_public_name
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


def _seed_client(
    owner_user_id: uuid.UUID,
    name: str,
    *,
    private_alias: str | None = None,
) -> uuid.UUID:
    with get_session_factory()() as session:
        stored = Client(
            owner_user_id=owner_user_id,
            public_name=name,
            normalized_public_name=normalize_public_name(name),
            private_alias=private_alias,
            profile_status=ClientProfileStatus.active,
        )
        session.add(stored)
        session.commit()
        return stored.id


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


def test_web_client_replace_requires_origin_and_updates_complete_card(client, create_user):
    owner = create_user(telegram_user_id=100000213)
    client_id = _seed_client(owner.id, "Анна", private_alias="внутреннее имя")
    _authenticate(client, owner.id)
    body = {
        "public_name": "Анна Петрова",
        "phone": "+7 922 222-22-22",
        "contact_channel": "Telegram",
        "birthday": "1990-05-14",
        "notes": "Предпочитает вечернее время",
        "nail_skin_notes": "Тонкие ногти",
        "sensitivity_notes": "Чувствительная кутикула",
        "style_preferences": "Зелёный и яркий дизайн",
        "communication_preferences": "Обращаться на вы",
    }

    missing_origin = client.put(f"/web/api/clients/{client_id}", json=body)
    assert missing_origin.status_code == 403
    assert missing_origin.json()["detail"]["code"] == "origin_required"

    response = client.put(
        f"/web/api/clients/{client_id}",
        headers=WEB_ORIGIN_HEADERS,
        json=body,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["changed"] is True
    assert set(result["changed_fields"]) == {
        "birthday",
        "communication_preferences",
        "contact_channel",
        "nail_skin_notes",
        "notes",
        "phone",
        "public_name",
        "sensitivity_notes",
        "style_preferences",
    }
    assert result["client"] == {
        "client_id": str(client_id),
        "public_name": "Анна Петрова",
        "phone": "+7 922 222-22-22",
        "contact_channel": "Telegram",
        "birthday": "1990-05-14",
        "notes": "Предпочитает вечернее время",
        "nail_skin_notes": "Тонкие ногти",
        "sensitivity_notes": "Чувствительная кутикула",
        "style_preferences": "Зелёный и яркий дизайн",
        "communication_preferences": "Обращаться на вы",
        "profile_status": "active",
        "updated_at": result["client"]["updated_at"],
    }

    card = client.get(
        f"/web/api/clients/{client_id}",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert card.status_code == 200
    assert card.json()["public_name"] == "Анна Петрова"
    assert card.json()["birthday"] == "1990-05-14"

    with get_session_factory()() as session:
        stored = session.get(Client, client_id)
        assert stored is not None
        assert stored.private_alias == "внутреннее имя"
        assert stored.birthday == date(1990, 5, 14)


def test_web_client_replace_is_owner_scoped(client, create_user):
    owner = create_user(telegram_user_id=100000214)
    other = create_user(telegram_user_id=100000215)
    other_client_id = _seed_client(other.id, "Чужая клиентка")
    _authenticate(client, owner.id)

    response = client.put(
        f"/web/api/clients/{other_client_id}",
        headers=WEB_ORIGIN_HEADERS,
        json={
            "public_name": "Изменённое имя",
            "phone": None,
            "contact_channel": None,
            "birthday": None,
            "notes": None,
            "nail_skin_notes": None,
            "sensitivity_notes": None,
            "style_preferences": None,
            "communication_preferences": None,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "client_not_found"
    with get_session_factory()() as session:
        stored = session.get(Client, other_client_id)
        assert stored is not None
        assert stored.public_name == "Чужая клиентка"


def test_web_client_replace_rejects_duplicate_name(client, create_user):
    owner = create_user(telegram_user_id=100000216)
    first_id = _seed_client(owner.id, "Первая")
    _seed_client(owner.id, "Вторая")
    _authenticate(client, owner.id)

    response = client.put(
        f"/web/api/clients/{first_id}",
        headers=WEB_ORIGIN_HEADERS,
        json={
            "public_name": "Вторая",
            "phone": None,
            "contact_channel": None,
            "birthday": None,
            "notes": None,
            "nail_skin_notes": None,
            "sensitivity_notes": None,
            "style_preferences": None,
            "communication_preferences": None,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "client_name_conflict"
