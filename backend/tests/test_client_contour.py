from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.client_models import ClientTelegramIdentity, ClientTelegramIdentityStatus
from app.db import get_session_factory
from app.models import AuditEvent, Client, Service
from app.services.normalization import normalize_public_name


def test_client_and_master_keys_are_separated(
    client,
    create_user,
    auth_headers,
    client_auth_headers,
):
    create_user()

    client_response = client.get(
        "/api/v1/client/catalog",
        headers=auth_headers(),
    )
    assert client_response.status_code == 401

    master_response = client.get(
        "/api/v1/scheduling/services",
        headers=client_auth_headers(),
    )
    assert master_response.status_code == 401


def test_public_catalog_is_owner_scoped_and_hides_internal_fields(
    client,
    create_user,
    create_service,
    client_auth_headers,
):
    owner = create_user()
    other_owner = create_user(telegram_user_id=100000002)
    create_service(owner.id, public_name="Маникюр")
    create_service(other_owner.id, public_name="Чужой прайс")

    response = client.get(
        "/api/v1/client/catalog",
        headers=client_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["public_name"] for item in payload["services"]] == ["Маникюр"]
    item = payload["services"][0]
    assert item["kind"] == "base"
    assert item["price_type"] == "fixed"
    assert item["price_amount"] == "2500.00"
    assert item["duration_minutes"] == 120
    forbidden = {
        "id",
        "owner_user_id",
        "buffer_before_minutes",
        "buffer_after_minutes",
        "is_active",
        "normalized_public_name",
    }
    assert forbidden.isdisjoint(item)


def test_public_slots_reuse_owner_schedule_without_exposing_buffers(
    client,
    create_user,
    create_service,
    create_availability,
    client_auth_headers,
):
    owner = create_user()
    create_service(
        owner.id,
        public_name="Маникюр",
        duration_minutes=120,
        buffer_before_minutes=10,
        buffer_after_minutes=20,
    )
    create_availability(owner.id, day=date(2026, 7, 18))

    response = client.get(
        "/api/v1/client/slots",
        params={"day": "2026-07-18", "service_name": "Маникюр"},
        headers=client_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"]["public_name"] == "Маникюр"
    assert payload["starts_at"][0].startswith("2026-07-18T11:15:00")
    assert "buffer_before_minutes" not in payload["service"]
    assert "buffer_after_minutes" not in payload["service"]
    assert "id" not in payload["service"]


def test_public_slots_reject_addon(
    client,
    create_user,
    client_auth_headers,
):
    owner = create_user()
    with get_session_factory()() as session:
        session.add(
            Service(
                owner_user_id=owner.id,
                public_name="Френч",
                normalized_public_name=normalize_public_name("Френч"),
                public_description=None,
                price_amount=Decimal("300.00"),
                currency="RUB",
                duration_minutes=1,
                buffer_before_minutes=0,
                buffer_after_minutes=0,
                is_active=True,
                kind="addon",
                price_type="fixed",
                sort_order=0,
                extra_minutes=15,
            )
        )
        session.commit()

    response = client.get(
        "/api/v1/client/slots",
        params={"day": "2026-07-18", "service_name": "Френч"},
        headers=client_auth_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "service_not_found"


def test_identity_registration_does_not_auto_link_existing_client(
    client,
    create_user,
    client_auth_headers,
):
    owner = create_user()
    with get_session_factory()() as session:
        existing = Client(
            owner_user_id=owner.id,
            public_name="Анна",
            normalized_public_name=normalize_public_name("Анна"),
            phone="+79990000000",
        )
        session.add(existing)
        session.commit()

    response = client.put(
        "/api/v1/client/identity",
        headers=client_auth_headers(telegram_user_id=200000001),
        json={
            "requested_public_name": "Анна",
            "requested_phone": "+79990000000",
            "contact_user_id": 200000001,
            "confirmed": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "identity": {
            "status": "pending",
            "display_name": "Анна",
            "phone_shared": True,
            "linked": False,
        },
        "created": True,
        "changed": True,
    }

    with get_session_factory()() as session:
        identity = session.scalar(select(ClientTelegramIdentity))
        assert identity is not None
        assert identity.owner_user_id == owner.id
        assert identity.client_id is None
        assert identity.status == ClientTelegramIdentityStatus.pending
        assert identity.telegram_user_id == 200000001

        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.action == "client_identity.registered")
        )
        assert audit is not None
        serialized = str(audit.safe_changes)
        assert "200000001" not in serialized
        assert "+79990000000" not in serialized
        assert "Анна" not in serialized
        assert audit.actor_user_id is None
        assert audit.safe_changes["actor_type"] == "client_bot"


def test_identity_contact_must_belong_to_transport_user(
    client,
    create_user,
    client_auth_headers,
):
    create_user()

    response = client.put(
        "/api/v1/client/identity",
        headers=client_auth_headers(telegram_user_id=200000001),
        json={
            "requested_public_name": "Анна",
            "requested_phone": "+79990000000",
            "contact_user_id": 200000002,
            "confirmed": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "client_contact_mismatch"


def test_identity_upsert_is_idempotent(
    client,
    create_user,
    client_auth_headers,
):
    create_user()
    body = {
        "requested_public_name": "Анна",
        "requested_phone": None,
        "contact_user_id": None,
        "confirmed": True,
    }

    first = client.put(
        "/api/v1/client/identity",
        headers=client_auth_headers(request_id="identity-first"),
        json=body,
    )
    second = client.put(
        "/api/v1/client/identity",
        headers=client_auth_headers(request_id="identity-second"),
        json=body,
    )

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["changed"] is False

    with get_session_factory()() as session:
        count = session.scalar(select(func.count()).select_from(ClientTelegramIdentity))
        audit_count = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.object_type == "client_telegram_identity")
        )
        assert count == 1
        assert audit_count == 1


def test_revoked_identity_cannot_be_reactivated_by_client(
    client,
    create_user,
    client_auth_headers,
):
    owner = create_user()
    with get_session_factory()() as session:
        session.add(
            ClientTelegramIdentity(
                owner_user_id=owner.id,
                telegram_user_id=200000001,
                status=ClientTelegramIdentityStatus.revoked,
                requested_public_name="Анна",
            )
        )
        session.commit()

    response = client.put(
        "/api/v1/client/identity",
        headers=client_auth_headers(),
        json={
            "requested_public_name": "Анна",
            "requested_phone": None,
            "contact_user_id": None,
            "confirmed": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "client_identity_revoked"
