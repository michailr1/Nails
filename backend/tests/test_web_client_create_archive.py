from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from conftest import WEB_ORIGIN_HEADERS
from sqlalchemy import func, select

from app.config import get_settings
from app.db import get_session_factory
from app.models import AuditEvent, Booking, Client, ClientProfileStatus, Service
from app.services.normalization import normalize_public_name
from app.services.web_auth import _keyed_hash
from app.web_auth_models import WebSession


def _authenticate(client, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    token = f"client-archive-session-{user_id}"
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
                request_id="web-client-archive-test",
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


def _create_client(client, name: str = "Анна") -> uuid.UUID:
    response = client.post(
        "/web/api/clients",
        headers=WEB_ORIGIN_HEADERS,
        json={"public_name": name, "phone": None},
    )
    assert response.status_code == 200
    assert response.json()["created"] is True
    return uuid.UUID(response.json()["client"]["client_id"])


def _create_booking(client) -> uuid.UUID:
    response = client.post(
        "/web/api/bookings",
        headers=WEB_ORIGIN_HEADERS,
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "addon_names": [],
            "starts_at": "2026-07-22T11:00:00+03:00",
            "price_override_amount": None,
            "duration_override_minutes": None,
            "idempotency_key": "archive-booking-1",
        },
    )
    assert response.status_code == 200
    assert response.json()["created"] is True
    return uuid.UUID(response.json()["booking"]["booking_id"])


def test_create_book_archive_preserves_history_and_hides_active_client(
    client,
    create_user,
):
    owner = create_user(telegram_user_id=100000301)
    _authenticate(client, owner.id)
    client_id = _create_client(client)
    _seed_service(owner.id)
    booking_id = _create_booking(client)

    response = client.post(
        f"/web/api/clients/{client_id}/archive",
        headers=WEB_ORIGIN_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"client_id": str(client_id), "archived": True}

    active = client.get("/web/api/clients")
    assert active.status_code == 200
    assert active.json()["clients"] == []

    with get_session_factory()() as session:
        stored_client = session.get(Client, client_id)
        assert stored_client is not None
        assert stored_client.profile_status == ClientProfileStatus.archived
        assert session.get(Booking, booking_id) is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(Booking)
                .where(Booking.client_id == client_id)
            )
            == 1
        )
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.owner_user_id == owner.id,
                AuditEvent.object_id == client_id,
                AuditEvent.action == "client.archived",
            )
        )
        assert audit is not None
        assert audit.safe_changes == {"changed_fields": ["profile_status"]}


def test_archive_returns_404_for_repeat_and_unknown_client(client, create_user):
    owner = create_user(telegram_user_id=100000302)
    _authenticate(client, owner.id)
    client_id = _create_client(client)

    first = client.post(
        f"/web/api/clients/{client_id}/archive",
        headers=WEB_ORIGIN_HEADERS,
    )
    repeated = client.post(
        f"/web/api/clients/{client_id}/archive",
        headers=WEB_ORIGIN_HEADERS,
    )
    unknown = client.post(
        f"/web/api/clients/{uuid.uuid4()}/archive",
        headers=WEB_ORIGIN_HEADERS,
    )

    assert first.status_code == 200
    assert repeated.status_code == 404
    assert repeated.json()["detail"]["code"] == "client_not_found"
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "client_not_found"


def test_archive_is_owner_scoped(client, create_user):
    owner = create_user(telegram_user_id=100000303)
    other = create_user(telegram_user_id=100000304)
    _authenticate(client, other.id)
    other_client_id = _create_client(client, "Чужая клиентка")

    _authenticate(client, owner.id)
    response = client.post(
        f"/web/api/clients/{other_client_id}/archive",
        headers=WEB_ORIGIN_HEADERS,
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "client_not_found"
    with get_session_factory()() as session:
        stored = session.get(Client, other_client_id)
        assert stored is not None
        assert stored.owner_user_id == other.id
        assert stored.profile_status == ClientProfileStatus.active
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.object_id == other_client_id,
                    AuditEvent.action == "client.archived",
                )
            )
            == 0
        )
