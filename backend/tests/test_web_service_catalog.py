from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from conftest import WEB_ORIGIN_HEADERS

from app.config import get_settings
from app.db import get_session_factory
from app.models import Service
from app.services.normalization import normalize_public_name
from app.services.web_auth import _keyed_hash
from app.web_auth_models import WebSession


def _authenticate(client, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    token = "service-session-" + str(user_id)
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
                created_ip_hash="a" * 64,
                last_ip_hash="a" * 64,
                request_id="web-service-catalog-test",
            )
        )
        session.commit()
    client.cookies.set("__Host-nails_session", token)


def _seed_service(owner_user_id: uuid.UUID, name: str, *, active: bool) -> None:
    with get_session_factory()() as session:
        session.add(
            Service(
                owner_user_id=owner_user_id,
                public_name=name,
                normalized_public_name=normalize_public_name(name),
                price_amount=Decimal("2500.00"),
                currency="RUB",
                duration_minutes=120,
                buffer_before_minutes=0,
                buffer_after_minutes=20,
                is_active=active,
                kind="base",
                price_type="fixed",
                sort_order=0,
                extra_minutes=0,
            )
        )
        session.commit()


def _service_payload(name: str, price: int) -> dict:
    return {
        "public_name": name,
        "public_description": None,
        "price_amount": price,
        "currency": "RUB",
        "duration_minutes": 100,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 15,
        "is_active": True,
        "kind": "base",
        "price_type": "fixed",
        "price_min_amount": None,
        "price_max_amount": None,
        "price_unit": None,
        "category": None,
        "sort_order": 0,
        "extra_minutes": 0,
    }


def test_web_catalog_lists_inactive_services_and_is_owner_scoped(client, create_user):
    owner = create_user(telegram_user_id=100000101)
    other = create_user(telegram_user_id=100000102)
    _seed_service(owner.id, "Маникюр", active=True)
    _seed_service(owner.id, "Старый дизайн", active=False)
    _seed_service(other.id, "Чужая услуга", active=True)
    _authenticate(client, owner.id)

    response = client.get("/web/api/services", headers=WEB_ORIGIN_HEADERS)

    assert response.status_code == 200
    services = response.json()["services"]
    assert {service["public_name"] for service in services} == {
        "Маникюр",
        "Старый дизайн",
    }
    assert {service["is_active"] for service in services} == {True, False}


def test_web_catalog_replace_is_atomic_verified_and_requires_origin(client, create_user):
    owner = create_user()
    _seed_service(owner.id, "Маникюр", active=True)
    _authenticate(client, owner.id)
    body = {"services": [_service_payload("Маникюр", 1700)]}

    missing_origin = client.put("/web/api/services/catalog", json=body)
    assert missing_origin.status_code == 403
    assert missing_origin.json()["detail"]["code"] == "origin_required"

    response = client.put(
        "/web/api/services/catalog",
        headers=WEB_ORIGIN_HEADERS,
        json=body,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["verified"] is True
    assert result["changed"] is True
    assert result["updated_count"] == 1
    assert result["services"][0]["price_amount"] == "1700.00"
    assert result["services"][0]["duration_minutes"] == 100
    assert result["services"][0]["buffer_after_minutes"] == 15
