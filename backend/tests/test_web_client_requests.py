from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from conftest import WEB_ORIGIN_HEADERS
from sqlalchemy import select

from app.client_models import (
    BookingRequest,
    BookingRequestStatus,
    ClientTelegramIdentity,
    ClientTelegramIdentityStatus,
)
from app.config import get_settings
from app.db import get_session_factory
from app.models import Booking, Client
from app.services.web_auth import _keyed_hash
from app.web_auth_models import WebSession

BERLIN = ZoneInfo("Europe/Berlin")


def _authenticate(client, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    token = "client-requests-session-" + str(user_id)
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
                request_id="web-client-requests-test",
            )
        )
        session.commit()
    client.cookies.set("__Host-nails_session", token)


def _seed_pending_request(owner_id: uuid.UUID, *, telegram_user_id: int, name: str, starts_at: datetime) -> BookingRequest:
    with get_session_factory()() as session:
        binding = ClientTelegramIdentity(
            owner_user_id=owner_id,
            telegram_user_id=telegram_user_id,
            status=ClientTelegramIdentityStatus.pending,
            requested_public_name=name,
        )
        session.add(binding)
        session.flush()
        request = BookingRequest(
            owner_user_id=owner_id,
            binding_id=binding.id,
            client_id=None,
            requested_public_name=name,
            service_name="Маникюр",
            addon_names=[],
            addon_quantities={},
            starts_at=starts_at,
            status=BookingRequestStatus.pending,
            idempotency_key=f"web-{telegram_user_id}",
        )
        session.add(request)
        session.commit()
        session.refresh(request)
        session.expunge(request)
        return request


def test_web_client_requests_list_is_owner_scoped(client, create_user):
    owner = create_user(telegram_user_id=840000001)
    other = create_user(telegram_user_id=840000002)
    starts_at = datetime.now(BERLIN) + timedelta(days=7)
    own = _seed_pending_request(owner.id, telegram_user_id=940000001, name="Анна", starts_at=starts_at)
    _seed_pending_request(other.id, telegram_user_id=940000002, name="Мария", starts_at=starts_at)
    _authenticate(client, owner.id)

    response = client.get("/web/api/client-requests", headers=WEB_ORIGIN_HEADERS)
    assert response.status_code == 200
    payload = response.json()["requests"]
    assert [item["id"] for item in payload] == [str(own.id)]
    assert payload[0]["requested_public_name"] == "Анна"
    assert payload[0]["status"] == "pending"


def test_web_client_request_approve_create_new_uses_existing_lifecycle(
    client,
    create_user,
    create_service,
    create_availability,
):
    owner = create_user(telegram_user_id=840000003)
    create_service(owner.id, public_name="Маникюр", duration_minutes=60, buffer_after_minutes=0)
    day = date.today() + timedelta(days=20)
    create_availability(owner.id, day=day, start_time=time(10), end_time=time(20))
    starts_at = datetime.combine(day, time(12), tzinfo=BERLIN)
    request = _seed_pending_request(owner.id, telegram_user_id=940000003, name="Анна Новая", starts_at=starts_at)
    _authenticate(client, owner.id)

    response = client.post(
        f"/web/api/client-requests/{request.id}/approve",
        headers=WEB_ORIGIN_HEADERS,
        json={"resolution": "create_new"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["booking_id"] is not None

    with get_session_factory()() as session:
        stored = session.get(BookingRequest, request.id)
        binding = session.get(ClientTelegramIdentity, request.binding_id)
        assert stored is not None and binding is not None
        assert stored.client_id is not None
        assert binding.client_id == stored.client_id
        assert binding.status == "active"
        assert session.get(Client, stored.client_id) is not None
        booking = session.get(Booking, stored.booking_id)
        assert booking is not None
        assert booking.owner_user_id == owner.id


def test_web_client_request_reject_keeps_other_owner_untouched(client, create_user):
    owner = create_user(telegram_user_id=840000004)
    other = create_user(telegram_user_id=840000005)
    starts_at = datetime.now(BERLIN) + timedelta(days=8)
    own = _seed_pending_request(owner.id, telegram_user_id=940000004, name="Анна", starts_at=starts_at)
    foreign = _seed_pending_request(other.id, telegram_user_id=940000005, name="Мария", starts_at=starts_at)
    _authenticate(client, owner.id)

    rejected = client.post(
        f"/web/api/client-requests/{own.id}/reject",
        headers=WEB_ORIGIN_HEADERS,
        json={},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    blocked = client.post(
        f"/web/api/client-requests/{foreign.id}/reject",
        headers=WEB_ORIGIN_HEADERS,
        json={},
    )
    assert blocked.status_code == 404

    with get_session_factory()() as session:
        assert session.get(BookingRequest, foreign.id).status == "pending"


def test_web_client_request_approve_can_link_explicit_existing_client(
    client,
    create_user,
    create_service,
    create_availability,
    create_client,
):
    owner = create_user(telegram_user_id=840000006)
    create_service(owner.id, public_name="Маникюр", duration_minutes=60, buffer_after_minutes=0)
    existing = create_client(owner.id, public_name="Постоянная Анна")
    day = date.today() + timedelta(days=21)
    create_availability(owner.id, day=day, start_time=time(10), end_time=time(20))
    starts_at = datetime.combine(day, time(14), tzinfo=BERLIN)
    request = _seed_pending_request(owner.id, telegram_user_id=940000006, name="Анна Telegram", starts_at=starts_at)
    _authenticate(client, owner.id)

    response = client.post(
        f"/web/api/client-requests/{request.id}/approve",
        headers=WEB_ORIGIN_HEADERS,
        json={"resolution": "link_existing", "client_id": str(existing.id)},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    with get_session_factory()() as session:
        stored = session.get(BookingRequest, request.id)
        assert stored is not None
        assert stored.client_id == existing.id
        assert session.scalar(select(Booking).where(Booking.id == stored.booking_id)) is not None
