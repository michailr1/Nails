from __future__ import annotations

from collections.abc import Callable

from conftest import WEB_ORIGIN_HEADERS
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import AuditEvent, OnboardingState, OnboardingStatus, User, UserRole


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
