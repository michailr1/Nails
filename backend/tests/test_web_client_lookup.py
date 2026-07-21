from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from conftest import WEB_ORIGIN_HEADERS

from app.config import get_settings
from app.db import get_session_factory
from app.models import Client, ClientProfileStatus
from app.services.normalization import normalize_public_name
from app.services.web_auth import _keyed_hash
from app.web_auth_models import WebSession


def _authenticate(client, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    token = "client-lookup-session-" + str(user_id)
    settings = get_settings()
    with get_session_factory()() as session:
        session.add(
            WebSession(
                token_hash=_keyed_hash(token, purpose="session-token", settings=settings),
                user_id=user_id,
                last_seen_at=now,
                idle_expires_at=now + timedelta(hours=1),
                absolute_expires_at=now + timedelta(days=1),
                rotation_counter=1,
                created_ip_hash="c" * 64,
                last_ip_hash="c" * 64,
                request_id="web-client-lookup-test",
            )
        )
        session.commit()
    client.cookies.set("__Host-nails_session", token)


def _seed_client(owner_user_id: uuid.UUID, name: str) -> uuid.UUID:
    with get_session_factory()() as session:
        stored = Client(
            owner_user_id=owner_user_id,
            public_name=name,
            normalized_public_name=normalize_public_name(name),
            profile_status=ClientProfileStatus.active,
        )
        session.add(stored)
        session.commit()
        return stored.id


def test_web_client_card_read_is_owner_scoped(client, create_user):
    owner = create_user(telegram_user_id=100000217)
    other = create_user(telegram_user_id=100000218)
    own_client_id = _seed_client(owner.id, "Своя клиентка")
    other_client_id = _seed_client(other.id, "Чужая клиентка")
    _authenticate(client, owner.id)

    own = client.get(
        f"/web/api/clients/{own_client_id}",
        headers=WEB_ORIGIN_HEADERS,
    )
    foreign = client.get(
        f"/web/api/clients/{other_client_id}",
        headers=WEB_ORIGIN_HEADERS,
    )

    assert own.status_code == 200
    assert own.json()["public_name"] == "Своя клиентка"
    assert foreign.status_code == 404
    assert foreign.json()["detail"]["code"] == "client_not_found"
