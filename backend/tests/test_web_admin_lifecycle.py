from __future__ import annotations

from collections.abc import Callable

from conftest import WEB_ORIGIN_HEADERS
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import AuditEvent, Client, User, UserRole
from app.web_auth_models import WebSession


def _login(
    client: TestClient,
    auth_headers: Callable[..., dict[str, str]],
    telegram_user_id: int,
) -> None:
    started = client.post("/web/api/auth/challenges", headers=WEB_ORIGIN_HEADERS)
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
    consumed = client.post(
        "/web/api/auth/challenges/consume",
        headers=WEB_ORIGIN_HEADERS,
        json={"challenge_id": payload["challenge_id"]},
    )
    assert consumed.status_code == 200


def test_admin_disables_master_without_deleting_business_data(
    client, create_user, auth_headers
):
    admin = create_user(telegram_user_id=750000001, role=UserRole.admin)
    master = create_user(telegram_user_id=750000002, role=UserRole.master)
    with get_session_factory()() as session:
        session.add(
            Client(
                owner_user_id=master.id,
                public_name="Сохранённая клиентка",
                normalized_public_name="сохранённая клиентка",
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

    disabled = client.post(
        f"/web/api/admin/masters/{master.id}/disable",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert disabled.status_code == 200
    assert disabled.json()["changed"] is True
    assert disabled.json()["master"]["is_active"] is False

    with get_session_factory()() as session:
        stored = session.get(User, master.id)
        assert stored is not None
        assert stored.is_active is False
        assert session.scalar(
            select(Client).where(Client.owner_user_id == master.id)
        ) is not None
        admin_session = session.scalar(
            select(WebSession).where(WebSession.user_id == admin.id)
        )
        assert admin_session is not None
        assert admin_session.target_owner_user_id is None
        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.action == "admin.master.disable")
        )
        assert audit is not None
        assert audit.actor_user_id == admin.id
        assert audit.owner_user_id == master.id


def test_admin_disable_is_idempotent_and_create_reactivates(
    client, create_user, auth_headers
):
    admin = create_user(telegram_user_id=760000001, role=UserRole.admin)
    master = create_user(
        telegram_user_id=760000002,
        role=UserRole.master,
        is_active=False,
    )
    _login(client, auth_headers, admin.telegram_user_id)

    disabled = client.post(
        f"/web/api/admin/masters/{master.id}/disable",
        headers=WEB_ORIGIN_HEADERS,
    )
    assert disabled.status_code == 200
    assert disabled.json()["changed"] is False

    reactivated = client.post(
        "/web/api/admin/masters",
        headers=WEB_ORIGIN_HEADERS,
        json={"telegram_user_id": master.telegram_user_id},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["created"] is False
    assert reactivated.json()["reactivated"] is True
    assert reactivated.json()["master"]["is_active"] is True

    with get_session_factory()() as session:
        assert session.scalar(
            select(AuditEvent).where(AuditEvent.action == "admin.master.reactivate")
        ) is not None
