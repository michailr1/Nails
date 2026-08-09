from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.client_models import (
    BookingRequest,
    ClientContactForward,
    MasterPublicProfile,
)
from app.db import get_session_factory
from app.models import Booking, Service
from app.services.client_binding import create_master_link_token

CLIENT_KEY = "c" * 64
INTERNAL_KEY = os.environ["INTERNAL_API_KEY"]
BERLIN = ZoneInfo("Europe/Berlin")


def _client_headers(telegram_user_id: int, binding_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
        "X-Request-ID": "request-edit-notify-290",
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = binding_id
    return headers


def _start_binding(client, master, telegram_user_id: int, name: str) -> str:
    with get_session_factory()() as session:
        session.add(
            MasterPublicProfile(owner_user_id=master.id, display_name="Мастер")
        )
        session.flush()
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()
    response = client.post(
        "/api/v1/client/start",
        headers=_client_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": name},
    )
    assert response.status_code == 200
    return response.json()["master"]["binding_id"]


def _create_request(client, telegram_user_id: int, binding_id: str, starts_at: str):
    return client.post(
        "/api/v1/client/requests",
        headers=_client_headers(telegram_user_id, binding_id),
        json={
            "service_name": "Маникюр",
            "addon_names": [],
            "addon_quantities": {},
            "starts_at": starts_at,
            "idempotency_key": "request-290-idempotent",
        },
    )


def test_new_request_enqueues_exactly_one_typed_master_forward(
    client,
    create_user,
    create_service,
):
    master = create_user(telegram_user_id=850000001)
    create_service(master.id, public_name="Маникюр", duration_minutes=60)
    binding_id = _start_binding(client, master, 950000001, "Алёна")
    day = date.today() + timedelta(days=14)
    starts_at = datetime.combine(day, time(14, 45), tzinfo=BERLIN).isoformat()

    first = _create_request(client, 950000001, binding_id, starts_at)
    second = _create_request(client, 950000001, binding_id, starts_at)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    with get_session_factory()() as session:
        forwards = session.scalars(
            select(ClientContactForward).where(
                ClientContactForward.owner_user_id == master.id,
                ClientContactForward.kind == "booking_request_created",
            )
        ).all()
        assert len(forwards) == 1
        forward = forwards[0]
        assert forward.dedupe_key == f"booking-request:{first.json()['id']}"
        assert forward.client_public_name == "Алёна"
        assert "Процедура: Маникюр" in forward.message_text
        assert "Время:" in forward.message_text
        assert "T14:45" not in forward.message_text

    claim = client.post(
        "/api/v1/client/contact-forward/internal/claim",
        headers={"X-Nails-Internal-Key": INTERNAL_KEY},
    )
    assert claim.status_code == 200
    payload = claim.json()
    assert payload["claimed"] is True
    assert payload["kind"] == "booking_request_created"
    assert payload["master_telegram_user_id"] == master.telegram_user_id
    assert payload["client_public_name"] == "Алёна"

    retry = client.post(
        "/api/v1/client/contact-forward/internal/ack",
        headers={"X-Nails-Internal-Key": INTERNAL_KEY},
        json={"claim_id": payload["claim_id"], "sent": False},
    )
    assert retry.status_code == 200
    claimed_again = client.post(
        "/api/v1/client/contact-forward/internal/claim",
        headers={"X-Nails-Internal-Key": INTERNAL_KEY},
    )
    assert claimed_again.status_code == 200
    assert claimed_again.json()["forward_id"] == payload["forward_id"]


def test_master_approval_uses_corrected_service_time_price_and_duration(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master = create_user(telegram_user_id=850000002)
    create_service(master.id, public_name="Маникюр", duration_minutes=60)
    create_service(master.id, public_name="Педикюр", duration_minutes=90)
    day = date.today() + timedelta(days=15)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(20))
    binding_id = _start_binding(client, master, 950000002, "Мария")
    requested = datetime.combine(day, time(11), tzinfo=BERLIN)
    corrected = datetime.combine(day, time(14), tzinfo=BERLIN)
    created = _create_request(client, 950000002, binding_id, requested.isoformat())
    assert created.status_code == 200

    approved = client.post(
        f"/api/v1/scheduling/client-requests/{created.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={
            "resolution": "create_new",
            "service_name": "Педикюр",
            "addon_names": [],
            "addon_quantities": {},
            "starts_at": corrected.isoformat(),
            "price_override_amount": 1234,
            "duration_override_minutes": 75,
        },
    )
    assert approved.status_code == 200, approved.text
    payload = approved.json()
    assert payload["status"] == "approved"
    assert payload["service_name"] == "Педикюр"
    assert datetime.fromisoformat(payload["starts_at"]).astimezone(BERLIN) == corrected

    with get_session_factory()() as session:
        request = session.get(BookingRequest, created.json()["id"])
        assert request is not None and request.booking_id is not None
        assert request.service_name == "Педикюр"
        assert request.starts_at.astimezone(BERLIN) == corrected
        booking = session.get(Booking, request.booking_id)
        assert booking is not None
        service = session.get(Service, booking.service_id)
        assert service is not None and service.public_name == "Педикюр"
        assert booking.duration_minutes_snapshot == 75
        assert booking.price_amount == Decimal("1234")


def test_failed_corrected_approval_leaves_request_pending_and_original_values(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master = create_user(telegram_user_id=850000003)
    create_service(master.id, public_name="Маникюр", duration_minutes=60)
    day = date.today() + timedelta(days=16)
    create_availability(master.id, day=day, is_available=False, start_time=None, end_time=None)
    binding_id = _start_binding(client, master, 950000003, "Елена")
    requested = datetime.combine(day, time(11), tzinfo=BERLIN)
    corrected = datetime.combine(day, time(15), tzinfo=BERLIN)
    created = _create_request(client, 950000003, binding_id, requested.isoformat())
    assert created.status_code == 200

    failed = client.post(
        f"/api/v1/scheduling/client-requests/{created.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={
            "resolution": "create_new",
            "service_name": "Маникюр",
            "addon_names": [],
            "addon_quantities": {},
            "starts_at": corrected.isoformat(),
        },
    )
    assert failed.status_code == 409
    assert failed.json()["detail"]["code"] == "booking_on_day_off"

    with get_session_factory()() as session:
        request = session.get(BookingRequest, created.json()["id"])
        assert request is not None
        assert request.status == "pending"
        assert request.booking_id is None
        assert request.service_name == "Маникюр"
        assert request.starts_at.astimezone(BERLIN) == requested
