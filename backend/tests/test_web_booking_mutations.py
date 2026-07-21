from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from conftest import WEB_ORIGIN_HEADERS

from app.config import get_settings
from app.db import get_session_factory
from app.models import Booking, Service
from app.services.normalization import normalize_public_name
from app.services.web_auth import _keyed_hash
from app.web_auth_models import WebSession


def _authenticate(client, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    token = f"booking-mutation-session-{user_id}"
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
                created_ip_hash="a" * 64,
                last_ip_hash="a" * 64,
                request_id="web-booking-mutation-test",
            )
        )
        session.commit()
    client.cookies.set("__Host-nails_session", token)


def _seed_service(owner_user_id: uuid.UUID) -> None:
    with get_session_factory()() as session:
        session.add(
            Service(
                owner_user_id=owner_user_id,
                public_name="Маникюр",
                normalized_public_name=normalize_public_name("Маникюр"),
                price_amount=Decimal("2500.00"),
                currency="RUB",
                duration_minutes=120,
                buffer_before_minutes=0,
                buffer_after_minutes=15,
                is_active=True,
                kind="base",
                price_type="fixed",
                category="Маникюр",
                sort_order=0,
                extra_minutes=0,
            )
        )
        session.commit()


def _create_booking(client, *, name: str, starts_at: str, key: str) -> uuid.UUID:
    created_client = client.post(
        "/web/api/clients",
        headers=WEB_ORIGIN_HEADERS,
        json={"public_name": name, "phone": None},
    )
    assert created_client.status_code == 200
    response = client.post(
        "/web/api/bookings",
        headers=WEB_ORIGIN_HEADERS,
        json={
            "client_public_name": name,
            "service_name": "Маникюр",
            "addon_names": [],
            "starts_at": starts_at,
            "price_override_amount": None,
            "duration_override_minutes": None,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 200
    return uuid.UUID(response.json()["booking"]["booking_id"])


def test_web_booking_can_be_rescheduled_and_cancelled(client, create_user):
    owner = create_user(telegram_user_id=100000401)
    _authenticate(client, owner.id)
    _seed_service(owner.id)
    booking_id = _create_booking(
        client,
        name="Анна",
        starts_at="2030-07-22T11:00:00+03:00",
        key="web-mutation-1",
    )

    moved = client.put(
        "/web/api/bookings/reschedule",
        headers=WEB_ORIGIN_HEADERS,
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "starts_at": "2030-07-22T11:00:00+03:00",
            "new_starts_at": "2030-07-22T14:00:00+03:00",
        },
    )
    assert moved.status_code == 200
    assert moved.json()["changed"] is True

    cancelled = client.put(
        "/web/api/bookings/cancel",
        headers=WEB_ORIGIN_HEADERS,
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "starts_at": "2030-07-22T14:00:00+03:00",
        },
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["changed"] is True

    with get_session_factory()() as session:
        stored = session.get(Booking, booking_id)
        assert stored is not None
        assert stored.status.value == "cancelled"
        assert stored.starts_at.isoformat() == "2030-07-22T11:00:00+00:00"


def test_web_booking_mutations_require_same_origin(client, create_user):
    owner = create_user(telegram_user_id=100000402)
    _authenticate(client, owner.id)

    response = client.put(
        "/web/api/bookings/cancel",
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "starts_at": "2030-07-22T11:00:00+03:00",
        },
    )

    assert response.status_code == 403


def test_booking_edit_assets_expose_only_future_active_actions():
    script = (
        __import__("pathlib").Path(__file__).parents[1]
        / "app"
        / "web_static"
        / "web-booking-edit.js"
    ).read_text(encoding="utf-8")

    assert 'booking.status === "scheduled"' in script
    assert 'new Date(booking.starts_at).getTime() > Date.now()' in script
    assert 'window.confirm(`Отменить запись' in script
    assert 'method: "PUT"' in script
    assert "/web/api/bookings/reschedule" in script
    assert "/web/api/bookings/cancel" in script
    assert "renderCalendar()" in script
    assert "sendMessage" not in script
