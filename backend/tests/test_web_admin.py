from __future__ import annotations

from collections.abc import Callable

from conftest import WEB_ORIGIN_HEADERS
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import (
    AuditEvent,
    Client,
    OnboardingState,
    OnboardingStatus,
    User,
    UserRole,
)


def _login(
    client: TestClient,
    auth_headers: Callable[..., dict[str, str]],
    telegram_user_id: int,
) -> None:
    started = client.post(
        "/web/api/auth/challenges",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert started.status_code == 201
    payload = started.json()
    approved = client.post(
        "/api/v1/web-auth/challenges/approve",
        headers=auth_headers(telegram_user_id),
        json={
            "challenge_id": payload["challenge_id"],
            "verification_number": payload["verification_number"],
        },
    )
    assert approved.status_code == 200
    assert approved.json() == {"approved": True}
    consumed = client.post(
        "/web/api/auth/challenges/consume",
        headers=WEB_ORIGIN_HEADERS,
        json={"challenge_id": payload["challenge_id"]},
    )
    assert consumed.status_code == 200
    assert consumed.json()["authenticated"] is True


def _calendar(client: TestClient):
    return client.get(
        "/web/api/calendar",
        headers=WEB_ORIGIN_HEADERS,
        params={"date_from": "2026-07-01", "date_to": "2026-07-31"},
    )


def test_admin_without_selection_has_consistent_non_401_read_contract(
    client, create_user, auth_headers
):
    admin = create_user(telegram_user_id=690000001, role=UserRole.admin)
    _login(client, auth_headers, admin.telegram_user_id)

    session_state = client.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    calendar = _calendar(client)
    clients = client.get("/web/api/clients", headers=WEB_ORIGIN_HEADERS)
    exported = client.post(
        "/web/api/exports/clients?format=csv",
        headers=WEB_ORIGIN_HEADERS,
        json={"master_user_id": str(admin.id)},
    )

    assert session_state.status_code == 200
    assert session_state.json() == {
        "authenticated": True,
        "role": "admin",
        "target_owner_user_id": None,
    }
    for response in (calendar, clients, exported):
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "select_master_required"


def test_master_session_reads_self_with_same_portal_role_contract(
    client, create_user, auth_headers
):
    master = create_user(telegram_user_id=690000002, role=UserRole.master)
    _login(client, auth_headers, master.telegram_user_id)

    session_state = client.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    calendar = _calendar(client)
    exported = client.post(
        "/web/api/exports/clients?format=csv",
        headers=WEB_ORIGIN_HEADERS,
    )

    assert session_state.status_code == 200
    assert session_state.json() == {
        "authenticated": True,
        "role": "master",
        "target_owner_user_id": None,
    }
    assert calendar.status_code == 200
    assert exported.status_code == 200


def test_admin_selects_master_reads_private_scope_and_audits(
    client, create_user, auth_headers
):
    admin = create_user(telegram_user_id=695000001, role=UserRole.admin)
    master = create_user(telegram_user_id=695000002, role=UserRole.master)
    with get_session_factory()() as session:
        session.add(
            Client(
                owner_user_id=master.id,
                public_name="Анна",
                normalized_public_name="анна",
                phone="+79990000000",
                notes="Предпочитает утро",
                sensitivity_notes="Чувствительная кожа",
            )
        )
        session.commit()

    _login(client, auth_headers, admin.telegram_user_id)
    selected = client.post(
        "/web/api/admin/select-master",
        headers=WEB_ORIGIN_HEADERS,
        json={"master_user_id": str(master.id)},
    )
    assert selected.status_code == 200
    assert selected.json()["master"]["id"] == str(master.id)

    session_state = client.get("/web/api/auth/session", headers=WEB_ORIGIN_HEADERS)
    clients = client.get("/web/api/clients", headers=WEB_ORIGIN_HEADERS)
    calendar = _calendar(client)
    exported = client.post(
        "/web/api/exports/clients?format=csv",
        headers=WEB_ORIGIN_HEADERS,
    )

    assert session_state.json()["target_owner_user_id"] == str(master.id)
    assert clients.status_code == 200
    assert clients.json()["clients"][0]["notes"] == "Предпочитает утро"
    assert clients.json()["clients"][0]["sensitivity_notes"] == "Чувствительная кожа"
    assert calendar.status_code == 200
    assert exported.status_code == 200

    with get_session_factory()() as session:
        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.action == "admin.master.scope.enter")
        )
        assert audit is not None
        assert audit.actor_user_id == admin.id
        assert audit.owner_user_id == master.id


def test_admin_cannot_mutate_selected_master_scope(client, create_user, auth_headers):
    admin = create_user(telegram_user_id=696000001, role=UserRole.admin)
    master = create_user(telegram_user_id=696000002, role=UserRole.master)
    _login(client, auth_headers, admin.telegram_user_id)
    selected = client.post(
        "/web/api/admin/select-master",
        headers=WEB_ORIGIN_HEADERS,
        json={"master_user_id": str(master.id)},
    )
    assert selected.status_code == 200

    mutation = client.post(
        "/web/api/clients",
        headers=WEB_ORIGIN_HEADERS,
        json={"public_name": "Нельзя", "phone": None},
    )
    assert mutation.status_code == 401

    with get_session_factory()() as session:
        stored = session.scalar(
            select(Client).where(
                Client.owner_user_id == master.id,
                Client.normalized_public_name == "нельзя",
            )
        )
        assert stored is None


def test_select_master_rejects_master_actor_and_inactive_target(
    client, create_user, auth_headers
):
    master_actor = create_user(telegram_user_id=697000001, role=UserRole.master)
    target = create_user(telegram_user_id=697000002, role=UserRole.master)
    _login(client, auth_headers, master_actor.telegram_user_id)
    forbidden = client.post(
        "/web/api/admin/select-master",
        headers=WEB_ORIGIN_HEADERS,
        json={"master_user_id": str(target.id)},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "admin_required"

    client.post("/web/api/auth/logout", headers=WEB_ORIGIN_HEADERS)
    admin = create_user(telegram_user_id=697000003, role=UserRole.admin)
    with get_session_factory()() as session:
        stored_target = session.get(User, target.id)
        assert stored_target is not None
        stored_target.is_active = False
        session.commit()
    _login(client, auth_headers, admin.telegram_user_id)
    missing = client.post(
        "/web/api/admin/select-master",
        headers=WEB_ORIGIN_HEADERS,
        json={"master_user_id": str(target.id)},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "active_master_not_found"


def test_admin_can_create_and_list_isolated_master(client, create_user, auth_headers):
    admin = create_user(telegram_user_id=700000001, role=UserRole.admin)
    _login(client, auth_headers, admin.telegram_user_id)

    created = client.post(
        "/web/api/admin/masters",
        headers=WEB_ORIGIN_HEADERS,
        json={"telegram_user_id": 700000002},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["created"] is True
    assert payload["master"]["telegram_user_id"] == 700000002
    assert payload["master"]["onboarding_status"] == "not_started"
    assert payload["master"]["is_active"] is True

    listed = client.get("/web/api/admin/masters")
    assert listed.status_code == 200
    assert [item["telegram_user_id"] for item in listed.json()["masters"]] == [
        700000002
    ]

    with get_session_factory()() as session:
        master = session.scalar(
            select(User).where(User.telegram_user_id == 700000002)
        )
        assert master is not None
        assert master.role == UserRole.master

        onboarding = session.scalar(
            select(OnboardingState).where(OnboardingState.user_id == master.id)
        )
        assert onboarding is not None
        assert onboarding.status == OnboardingStatus.not_started

        stored_admin = session.scalar(select(User).where(User.id == admin.id))
        assert stored_admin is not None
        assert stored_admin.role == UserRole.admin

        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.action == "admin.master.create")
        )
        assert audit is not None


def test_admin_create_is_idempotent(client, create_user, auth_headers):
    admin = create_user(telegram_user_id=710000001, role=UserRole.admin)
    create_user(telegram_user_id=710000002, role=UserRole.master)
    _login(client, auth_headers, admin.telegram_user_id)

    response = client.post(
        "/web/api/admin/masters",
        headers=WEB_ORIGIN_HEADERS,
        json={"telegram_user_id": 710000002},
    )
    assert response.status_code == 200
    assert response.json()["created"] is False

    with get_session_factory()() as session:
        users = session.scalars(
            select(User).where(User.telegram_user_id == 710000002)
        ).all()
        assert len(users) == 1


def test_admin_cannot_rebind_existing_admin_identity(client, create_user, auth_headers):
    admin = create_user(telegram_user_id=720000001, role=UserRole.admin)
    _login(client, auth_headers, admin.telegram_user_id)

    response = client.post(
        "/web/api/admin/masters",
        headers=WEB_ORIGIN_HEADERS,
        json={"telegram_user_id": admin.telegram_user_id},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "telegram_identity_conflict"


def test_master_cannot_access_admin_endpoints(client, create_user, auth_headers):
    master = create_user(telegram_user_id=730000001, role=UserRole.master)
    _login(client, auth_headers, master.telegram_user_id)

    listed = client.get("/web/api/admin/masters")
    assert listed.status_code == 403
    assert listed.json()["detail"]["code"] == "admin_required"

    created = client.post(
        "/web/api/admin/masters",
        headers=WEB_ORIGIN_HEADERS,
        json={"telegram_user_id": 730000002},
    )
    assert created.status_code == 403
    assert created.json()["detail"]["code"] == "admin_required"

    with get_session_factory()() as session:
        stored = session.scalar(
            select(User).where(User.telegram_user_id == 730000002)
        )
        assert stored is None


def test_admin_write_requires_web_boundary(client, create_user, auth_headers):
    admin = create_user(telegram_user_id=740000001, role=UserRole.admin)
    _login(client, auth_headers, admin.telegram_user_id)

    response = client.post(
        "/web/api/admin/masters",
        json={"telegram_user_id": 740000002},
    )
    assert response.status_code == 403
