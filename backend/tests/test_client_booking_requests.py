from __future__ import annotations

from datetime import datetime

from app.client_models import ClientTelegramIdentity, MasterPublicProfile
from app.db import get_session_factory
from app.models import Client
from app.services.normalization import normalize_public_name
from conftest import TEST_CLIENT_INTERNAL_API_KEY


def _client_headers(telegram_user_id: int, binding_id) -> dict[str, str]:
    return {
        "X-Nails-Client-Internal-Key": TEST_CLIENT_INTERNAL_API_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
        "X-Client-Binding-ID": str(binding_id),
        "X-Request-ID": "client-booking-request-test",
    }


def _active_binding(master, telegram_user_id: int, name: str = "Анна"):
    with get_session_factory()() as session:
        profile = MasterPublicProfile(owner_user_id=master.id, display_name="Мастер")
        client = Client(
            owner_user_id=master.id,
            public_name=name,
            normalized_public_name=normalize_public_name(name),
        )
        session.add_all([profile, client])
        session.flush()
        binding = ClientTelegramIdentity(
            owner_user_id=master.id,
            client_id=client.id,
            telegram_user_id=telegram_user_id,
            status="active",
            requested_public_name=name,
        )
        session.add(binding)
        session.commit()
        session.refresh(binding)
        return binding.id


def test_pending_request_does_not_reserve_slot_and_client_can_cancel(
    client,
    create_user,
    create_service,
    create_availability,
):
    master = create_user(telegram_user_id=830000001)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_after_minutes=0,
    )
    create_availability(master.id)
    binding_id = _active_binding(master, 930000001)
    headers = _client_headers(930000001, binding_id)
    starts_at = "2026-07-18T11:00:00+02:00"

    created = client.post(
        "/api/v1/client/requests",
        headers=headers,
        json={
            "service_name": "Маникюр",
            "addon_names": [],
            "addon_quantities": {},
            "starts_at": starts_at,
            "idempotency_key": "request-1",
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "pending"
    assert created.json()["booking_id"] is None

    slots = client.get(
        "/api/v1/client/slots",
        headers=headers,
        params={"day": "2026-07-18", "service_name": "Маникюр"},
    )
    assert slots.status_code == 200
    assert starts_at in slots.json()["starts_at"]

    cancelled = client.post(
        f"/api/v1/client/requests/{created.json()['id']}/cancel",
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_request_is_owner_and_binding_scoped(client, create_user, create_service):
    master_a = create_user(telegram_user_id=830000002)
    master_b = create_user(telegram_user_id=830000003)
    create_service(master_a.id, public_name="Маникюр")
    create_service(master_b.id, public_name="Маникюр")
    binding_a = _active_binding(master_a, 930000002, "Анна А")
    binding_b = _active_binding(master_b, 930000002, "Анна Б")

    created = client.post(
        "/api/v1/client/requests",
        headers=_client_headers(930000002, binding_a),
        json={
            "service_name": "Маникюр",
            "starts_at": "2026-07-18T11:00:00+02:00",
            "idempotency_key": "owner-a-request",
        },
    )
    assert created.status_code == 200

    other = client.get(
        "/api/v1/client/requests",
        headers=_client_headers(930000002, binding_b),
    )
    assert other.status_code == 200
    assert other.json()["requests"] == []


def test_master_approve_reuses_booking_domain_and_is_recoverably_idempotent(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master = create_user(telegram_user_id=830000004)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_after_minutes=0,
    )
    create_availability(master.id)
    binding_id = _active_binding(master, 930000004)

    created = client.post(
        "/api/v1/client/requests",
        headers=_client_headers(930000004, binding_id),
        json={
            "service_name": "Маникюр",
            "starts_at": "2026-07-18T11:00:00+02:00",
            "idempotency_key": "approve-request",
        },
    )
    request_id = created.json()["id"]

    approved = client.post(
        f"/api/v1/scheduling/client-requests/{request_id}/approve",
        headers=auth_headers(master.telegram_user_id),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    booking_id = approved.json()["booking_id"]
    assert booking_id is not None

    retried = client.post(
        f"/api/v1/scheduling/client-requests/{request_id}/approve",
        headers=auth_headers(master.telegram_user_id),
    )
    assert retried.status_code == 200
    assert retried.json()["booking_id"] == booking_id

    slots = client.get(
        "/api/v1/client/slots",
        headers=_client_headers(930000004, binding_id),
        params={"day": "2026-07-18", "service_name": "Маникюр"},
    )
    assert slots.status_code == 200
    assert "2026-07-18T11:00:00+02:00" not in slots.json()["starts_at"]


def test_request_payload_forbids_owner_client_and_role_override(
    client,
    create_user,
):
    master = create_user(telegram_user_id=830000005)
    binding_id = _active_binding(master, 930000005)
    response = client.post(
        "/api/v1/client/requests",
        headers=_client_headers(930000005, binding_id),
        json={
            "service_name": "Маникюр",
            "starts_at": datetime(2026, 7, 18, 11, 0).astimezone().isoformat(),
            "idempotency_key": "forbidden-fields",
            "owner_user_id": str(master.id),
            "client_id": str(master.id),
            "role": "master",
        },
    )
    assert response.status_code == 422
