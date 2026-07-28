from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.client_models import BookingRequest, ClientTelegramIdentity, MasterPublicProfile
from app.db import get_session_factory
from app.models import AuditEvent, Client
from app.services.client_binding import create_master_link_token
from app.services.normalization import normalize_public_name

CLIENT_KEY = "c" * 64
BERLIN = ZoneInfo("Europe/Berlin")


def _client_headers(telegram_user_id: int, binding_id=None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
        "X-Request-ID": "client-booking-request-test",
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = str(binding_id)
    return headers


def _future_start(hour: int = 11) -> tuple[date, str]:
    day = date.today() + timedelta(days=30)
    value = datetime.combine(day, time(hour, 0), tzinfo=BERLIN)
    return day, value.isoformat()


def _start_binding(client, master, telegram_user_id: int, name: str = "Анна"):
    with get_session_factory()() as session:
        profile = session.get(MasterPublicProfile, master.id)
        if profile is None:
            session.add(
                MasterPublicProfile(owner_user_id=master.id, display_name="Мастер")
            )
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()

    response = client.post(
        "/api/v1/client/start",
        headers=_client_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": name},
    )
    assert response.status_code == 200
    assert response.json()["state"] == "ready"
    return response.json()["master"]["binding_id"]


def _create_client(master, name: str) -> Client:
    with get_session_factory()() as session:
        row = Client(
            owner_user_id=master.id,
            public_name=name,
            normalized_public_name=normalize_public_name(name),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row


def _create_request(client, telegram_user_id, binding_id, starts_at, **overrides):
    payload = {
        "service_name": "Маникюр",
        "addon_names": [],
        "addon_quantities": {},
        "starts_at": starts_at,
        "idempotency_key": f"request-{telegram_user_id}-{starts_at}",
    }
    payload.update(overrides)
    return client.post(
        "/api/v1/client/requests",
        headers=_client_headers(telegram_user_id, binding_id),
        json=payload,
    )


def test_first_request_from_start_pending_binding_is_reachable_and_does_not_reserve(
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
    day, starts_at = _future_start()
    create_availability(master.id, day=day)
    binding_id = _start_binding(client, master, 930000001, "Анна Первая")

    created = _create_request(client, 930000001, binding_id, starts_at)
    assert created.status_code == 200
    assert created.json()["status"] == "pending"
    assert created.json()["requested_public_name"] == "Анна Первая"
    assert created.json()["booking_id"] is None

    with get_session_factory()() as session:
        binding = session.get(ClientTelegramIdentity, binding_id)
        request = session.get(BookingRequest, created.json()["id"])
        assert binding is not None and request is not None
        assert binding.status == "pending"
        assert binding.client_id is None
        assert request.client_id is None

    slots = client.get(
        "/api/v1/client/slots",
        headers=_client_headers(930000001, binding_id),
        params={"day": day.isoformat(), "service_name": "Маникюр"},
    )
    assert slots.status_code == 200
    assert starts_at in slots.json()["starts_at"]

    cancelled = client.post(
        f"/api/v1/client/requests/{created.json()['id']}/cancel",
        headers=_client_headers(930000001, binding_id),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_master_approve_create_new_resolves_binding_and_is_idempotent(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master = create_user(telegram_user_id=830000002)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_after_minutes=0,
    )
    day, starts_at = _future_start()
    create_availability(master.id, day=day)
    binding_id = _start_binding(client, master, 930000002, "Анна Новая")
    created = _create_request(client, 930000002, binding_id, starts_at)
    assert created.status_code == 200

    approved = client.post(
        f"/api/v1/scheduling/client-requests/{created.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={"resolution": "create_new"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    booking_id = approved.json()["booking_id"]
    assert booking_id is not None

    with get_session_factory()() as session:
        binding = session.get(ClientTelegramIdentity, binding_id)
        request = session.get(BookingRequest, created.json()["id"])
        assert binding is not None and request is not None
        assert binding.status == "active"
        assert binding.client_id is not None
        assert request.client_id == binding.client_id
        resolved = session.get(Client, binding.client_id)
        assert resolved is not None
        assert resolved.public_name == "Анна Новая"

    retried = client.post(
        f"/api/v1/scheduling/client-requests/{created.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={"resolution": "create_new"},
    )
    assert retried.status_code == 200
    assert retried.json()["booking_id"] == booking_id

    slots = client.get(
        "/api/v1/client/slots",
        headers=_client_headers(930000002, binding_id),
        params={"day": day.isoformat(), "service_name": "Маникюр"},
    )
    assert slots.status_code == 200
    assert starts_at not in slots.json()["starts_at"]


def test_master_can_explicitly_link_existing_client(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master = create_user(telegram_user_id=830000003)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_after_minutes=0,
    )
    existing = _create_client(master, "Анна Карточка")
    day, starts_at = _future_start()
    create_availability(master.id, day=day)
    binding_id = _start_binding(client, master, 930000003, "Анна из Telegram")
    created = _create_request(client, 930000003, binding_id, starts_at)

    approved = client.post(
        f"/api/v1/scheduling/client-requests/{created.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={"resolution": "link_existing", "client_id": str(existing.id)},
    )
    assert approved.status_code == 200

    with get_session_factory()() as session:
        binding = session.get(ClientTelegramIdentity, binding_id)
        request = session.get(BookingRequest, created.json()["id"])
        assert binding is not None and request is not None
        assert binding.status == "active"
        assert binding.client_id == existing.id
        assert request.client_id == existing.id


def test_name_match_never_auto_links_existing_card(
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
    existing = _create_client(master, "Анна")
    day, starts_at = _future_start()
    create_availability(master.id, day=day)
    binding_id = _start_binding(client, master, 930000004, "Анна")
    created = _create_request(client, 930000004, binding_id, starts_at)
    assert created.status_code == 200

    with get_session_factory()() as session:
        binding = session.get(ClientTelegramIdentity, binding_id)
        assert binding is not None
        assert binding.status == "pending"
        assert binding.client_id is None

    create_new = client.post(
        f"/api/v1/scheduling/client-requests/{created.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={"resolution": "create_new"},
    )
    assert create_new.status_code == 409
    assert create_new.json()["detail"]["code"] == "client_name_conflict"

    explicit = client.post(
        f"/api/v1/scheduling/client-requests/{created.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={"resolution": "link_existing", "client_id": str(existing.id)},
    )
    assert explicit.status_code == 200


def test_existing_card_bound_to_other_active_identity_cannot_be_selected(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master = create_user(telegram_user_id=830000005)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_after_minutes=0,
    )
    existing = _create_client(master, "Общая Анна")
    day = date.today() + timedelta(days=30)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(20))

    first_binding = _start_binding(client, master, 930000005, "Первая")
    first_start = datetime.combine(day, time(11), tzinfo=BERLIN).isoformat()
    first = _create_request(client, 930000005, first_binding, first_start)
    first_approved = client.post(
        f"/api/v1/scheduling/client-requests/{first.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={"resolution": "link_existing", "client_id": str(existing.id)},
    )
    assert first_approved.status_code == 200

    second_binding = _start_binding(client, master, 930000006, "Вторая")
    second_start = datetime.combine(day, time(14), tzinfo=BERLIN).isoformat()
    second = _create_request(client, 930000006, second_binding, second_start)
    blocked = client.post(
        f"/api/v1/scheduling/client-requests/{second.json()['id']}/approve",
        headers=auth_headers(master.telegram_user_id),
        json={"resolution": "link_existing", "client_id": str(existing.id)},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "client_already_linked"


def test_request_is_owner_and_binding_scoped(client, create_user, create_service):
    master_a = create_user(telegram_user_id=830000006)
    master_b = create_user(telegram_user_id=830000007)
    create_service(master_a.id, public_name="Маникюр")
    create_service(master_b.id, public_name="Маникюр")
    binding_a = _start_binding(client, master_a, 930000007, "Анна А")
    binding_b = _start_binding(client, master_b, 930000007, "Анна Б")
    _, starts_at = _future_start()

    created = _create_request(client, 930000007, binding_a, starts_at)
    assert created.status_code == 200
    other = client.get(
        "/api/v1/client/requests",
        headers=_client_headers(930000007, binding_b),
    )
    assert other.status_code == 200
    assert other.json()["requests"] == []


def test_request_rejects_past_time_and_missing_service_at_entry(
    client,
    create_user,
    create_service,
):
    master = create_user(telegram_user_id=830000008)
    create_service(master.id, public_name="Маникюр")
    binding_id = _start_binding(client, master, 930000008)

    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    rejected_past = _create_request(client, 930000008, binding_id, past)
    assert rejected_past.status_code == 422
    assert rejected_past.json()["detail"]["code"] == "booking_request_start_in_past"

    _, future = _future_start()
    missing = _create_request(
        client,
        930000008,
        binding_id,
        future,
        service_name="Несуществующая услуга",
        idempotency_key="missing-service",
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "service_not_found"


def test_client_mutation_audit_marks_client_bot_without_identity_pii(
    client,
    create_user,
    create_service,
):
    master = create_user(telegram_user_id=830000009)
    create_service(master.id, public_name="Маникюр")
    binding_id = _start_binding(client, master, 930000009, "Секретное Имя")
    _, starts_at = _future_start()
    created = _create_request(client, 930000009, binding_id, starts_at)
    assert created.status_code == 200
    cancelled = client.post(
        f"/api/v1/client/requests/{created.json()['id']}/cancel",
        headers=_client_headers(930000009, binding_id),
    )
    assert cancelled.status_code == 200

    with get_session_factory()() as session:
        events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.action.in_(
                    ("client_booking_request.created", "client_booking_request.cancelled")
                )
            )
        ).all()
        assert len(events) == 2
        for event in events:
            assert event.safe_changes["actor_type"] == "client_bot"
            serialized = str(event.safe_changes)
            assert "Секретное Имя" not in serialized
            assert "930000009" not in serialized
            assert "phone" not in serialized.casefold()


def test_master_status_filter_returns_only_pending(
    client,
    create_user,
    create_service,
    auth_headers,
):
    master = create_user(telegram_user_id=830000010)
    create_service(master.id, public_name="Маникюр")
    binding_id = _start_binding(client, master, 930000010)
    day = date.today() + timedelta(days=30)
    first_start = datetime.combine(day, time(11), tzinfo=BERLIN).isoformat()
    second_start = datetime.combine(day, time(15), tzinfo=BERLIN).isoformat()
    pending = _create_request(
        client,
        930000010,
        binding_id,
        first_start,
        idempotency_key="pending",
    )
    rejected = _create_request(
        client,
        930000010,
        binding_id,
        second_start,
        idempotency_key="rejected",
    )
    assert pending.status_code == 200 and rejected.status_code == 200
    rejected_response = client.post(
        f"/api/v1/scheduling/client-requests/{rejected.json()['id']}/reject",
        headers=auth_headers(master.telegram_user_id),
    )
    assert rejected_response.status_code == 200

    response = client.get(
        "/api/v1/scheduling/client-requests",
        headers=auth_headers(master.telegram_user_id),
        params={"status": "pending"},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["requests"]] == [
        pending.json()["id"]
    ]


def test_approved_request_requires_booking_id_at_database_boundary(
    client,
    create_user,
    create_service,
):
    master = create_user(telegram_user_id=830000011)
    create_service(master.id, public_name="Маникюр")
    binding_id = _start_binding(client, master, 930000011)
    _, starts_at = _future_start()
    created = _create_request(client, 930000011, binding_id, starts_at)
    assert created.status_code == 200

    with get_session_factory()() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "UPDATE booking_requests SET status = 'approved' "
                    "WHERE id = :request_id"
                ),
                {"request_id": created.json()["id"]},
            )
            session.commit()


def test_request_payload_forbids_owner_client_and_role_override(
    client,
    create_user,
    create_service,
):
    master = create_user(telegram_user_id=830000012)
    create_service(master.id, public_name="Маникюр")
    binding_id = _start_binding(client, master, 930000012)
    _, starts_at = _future_start()
    response = client.post(
        "/api/v1/client/requests",
        headers=_client_headers(930000012, binding_id),
        json={
            "service_name": "Маникюр",
            "starts_at": starts_at,
            "idempotency_key": "forbidden-fields",
            "owner_user_id": str(master.id),
            "client_id": str(master.id),
            "role": "master",
        },
    )
    assert response.status_code == 422
