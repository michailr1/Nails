from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from conftest import WEB_ORIGIN_HEADERS
from sqlalchemy import func, select

from app.config import get_settings
from app.db import get_session_factory
from app.models import Booking, Client, ClientProfileStatus, Service
from app.services.normalization import normalize_public_name
from app.services.web_auth import _keyed_hash
from app.web_auth_models import WebSession


def _authenticate(client, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    token = "booking-session-" + str(user_id)
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
                request_id="web-booking-test",
            )
        )
        session.commit()
    client.cookies.set("__Host-nails_session", token)


def _seed_client(owner_user_id: uuid.UUID, name: str) -> None:
    with get_session_factory()() as session:
        session.add(
            Client(
                owner_user_id=owner_user_id,
                public_name=name,
                normalized_public_name=normalize_public_name(name),
                profile_status=ClientProfileStatus.active,
            )
        )
        session.commit()


def _seed_service(
    owner_user_id: uuid.UUID,
    name: str,
    *,
    kind: str,
    price_type: str = "fixed",
    price_amount: str = "0",
    duration_minutes: int = 1,
    extra_minutes: int = 0,
    price_unit: str | None = None,
) -> None:
    with get_session_factory()() as session:
        session.add(
            Service(
                owner_user_id=owner_user_id,
                public_name=name,
                normalized_public_name=normalize_public_name(name),
                price_amount=Decimal(price_amount),
                currency="RUB",
                duration_minutes=duration_minutes,
                buffer_before_minutes=0,
                buffer_after_minutes=15 if kind == "base" else 0,
                is_active=True,
                kind=kind,
                price_type=price_type,
                price_unit=price_unit,
                category="Маникюр" if kind == "base" else "Дополнительно",
                sort_order=0,
                extra_minutes=extra_minutes,
            )
        )
        session.commit()


def _payload(
    *,
    key: str,
    addons: list[str] | None = None,
    starts_at: str = "2026-07-22T11:00:00+02:00",
) -> dict:
    return {
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "addon_names": addons or [],
        "starts_at": starts_at,
        "price_override_amount": None,
        "duration_override_minutes": None,
        "idempotency_key": key,
    }


def test_web_booking_requires_origin_and_creates_verified_composition(client, create_user):
    owner = create_user(telegram_user_id=100000201)
    _seed_client(owner.id, "Анна")
    _seed_service(
        owner.id,
        "Маникюр",
        kind="base",
        price_amount="1200",
        duration_minutes=90,
    )
    _seed_service(
        owner.id,
        "Френч",
        kind="addon",
        price_amount="300",
        extra_minutes=20,
    )
    _authenticate(client, owner.id)
    body = _payload(key="web-booking-1", addons=["Френч"])

    missing_origin = client.post("/web/api/bookings", json=body)
    assert missing_origin.status_code == 403
    assert missing_origin.json()["detail"]["code"] == "origin_required"

    response = client.post(
        "/web/api/bookings",
        headers=WEB_ORIGIN_HEADERS,
        json=body,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["created"] is True
    assert result["booking"]["client_name"] == "Анна"
    assert result["booking"]["service_name"] == "Маникюр"
    assert result["booking"]["addon_names"] == ["Френч"]
    assert result["booking"]["duration_minutes"] == 110
    assert result["booking"]["price_amount"] == "1500.00"
    assert result["booking"]["price_type"] == "fixed"

    repeated = client.post(
        "/web/api/bookings",
        headers=WEB_ORIGIN_HEADERS,
        json=body,
    )
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False

    with get_session_factory()() as session:
        assert session.scalar(select(func.count()).select_from(Booking)) == 1

    calendar = client.get(
        "/web/api/calendar",
        headers=WEB_ORIGIN_HEADERS,
        params={"date_from": "2026-07-22", "date_to": "2026-07-22"},
    )
    assert calendar.status_code == 200
    booking = calendar.json()["bookings"][0]
    assert booking["addon_names"] == ["Френч"]
    assert booking["duration_minutes"] == 110
    assert booking["price_amount"] == "1500.00"


def test_web_booking_keeps_mixed_per_unit_price_unknown_instead_of_zero(client, create_user):
    owner = create_user(telegram_user_id=100000202)
    _seed_client(owner.id, "Анна")
    _seed_service(
        owner.id,
        "Маникюр",
        kind="base",
        price_amount="1200",
        duration_minutes=90,
    )
    _seed_service(
        owner.id,
        "Дизайн за ноготь",
        kind="addon",
        price_type="per_unit",
        price_amount="50",
        extra_minutes=10,
        price_unit="ноготь",
    )
    _authenticate(client, owner.id)

    response = client.post(
        "/web/api/bookings",
        headers=WEB_ORIGIN_HEADERS,
        json=_payload(key="web-booking-unit", addons=["Дизайн за ноготь"]),
    )

    assert response.status_code == 200
    booking = response.json()["booking"]
    assert booking["price_amount"] is None
    assert booking["price_type"] == "on_request"
    assert booking["price_confirmed"] is False

    calendar = client.get(
        "/web/api/calendar",
        headers=WEB_ORIGIN_HEADERS,
        params={"date_from": "2026-07-22", "date_to": "2026-07-22"},
    )
    assert calendar.status_code == 200
    assert calendar.json()["bookings"][0]["price_amount"] is None


def test_web_booking_is_owner_scoped(client, create_user):
    owner = create_user(telegram_user_id=100000203)
    other = create_user(telegram_user_id=100000204)
    _seed_client(owner.id, "Анна")
    _seed_service(
        owner.id,
        "Маникюр",
        kind="base",
        price_amount="1200",
        duration_minutes=90,
    )
    _seed_client(other.id, "Чужая клиентка")
    _seed_service(
        other.id,
        "Чужая процедура",
        kind="base",
        price_amount="5000",
        duration_minutes=120,
    )
    _authenticate(client, owner.id)

    body = _payload(key="web-booking-owner")
    body["client_public_name"] = "Чужая клиентка"
    body["service_name"] = "Чужая процедура"
    response = client.post(
        "/web/api/bookings",
        headers=WEB_ORIGIN_HEADERS,
        json=body,
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "client_not_found"
    with get_session_factory()() as session:
        assert session.scalar(select(func.count()).select_from(Booking)) == 0
