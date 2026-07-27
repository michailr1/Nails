from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.client_models import ClientTelegramIdentity, MasterPublicProfile
from app.db import get_session_factory
from app.models import UserRole
from app.services.client_binding import (
    ClientBindingError,
    create_master_link_token,
    list_client_masters,
    resolve_start_token,
    revoke_master_link_token,
)


def _profile(session, owner, name: str, contact: str | None = None) -> None:
    session.add(
        MasterPublicProfile(
            owner_user_id=owner.id,
            display_name=name,
            public_contact=contact,
        )
    )
    session.flush()


def test_start_token_resolves_owner_server_side_without_identity_leak(create_user):
    master = create_user(telegram_user_id=810000001)
    with get_session_factory()() as session:
        _profile(session, master, "Студия Лак", "@studio_lak")
        link = create_master_link_token(session, owner_user_id=master.id)
        session.commit()

        context = resolve_start_token(
            session,
            start_token=link.token,
            telegram_user_id=910000001,
        )
        assert context.owner_user_id == master.id
        assert context.master.display_name == "Студия Лак"
        assert context.master.public_contact == "@studio_lak"
        public_projection = {
            "display_name": context.master.display_name,
            "public_contact": context.master.public_contact,
        }
        serialized = str(public_projection)
        assert str(master.telegram_user_id) not in serialized
        assert "telegram_user_id" not in public_projection


def test_public_contact_is_opt_in_only(create_user):
    master = create_user(telegram_user_id=810000002)
    with get_session_factory()() as session:
        _profile(session, master, "Мастер А")
        link = create_master_link_token(session, owner_user_id=master.id)
        session.commit()
        context = resolve_start_token(
            session,
            start_token=link.token,
            telegram_user_id=910000002,
        )
        assert context.master.public_contact is None


def test_link_activation_requires_public_display_name(create_user):
    master = create_user(telegram_user_id=810000003)
    with (
        get_session_factory()() as session,
        pytest.raises(ClientBindingError, match="master_link_inactive"),
    ):
        create_master_link_token(session, owner_user_id=master.id)


def test_link_activation_requires_active_master(create_user):
    inactive_master = create_user(telegram_user_id=810000008, is_active=False)
    with get_session_factory()() as session:
        _profile(session, inactive_master, "Отключённый мастер")
        with pytest.raises(ClientBindingError, match="master_unavailable"):
            create_master_link_token(session, owner_user_id=inactive_master.id)


def test_link_activation_rejects_non_master(create_user):
    admin = create_user(telegram_user_id=810000009, role=UserRole.admin)
    with get_session_factory()() as session:
        _profile(session, admin, "Администратор")
        with pytest.raises(ClientBindingError, match="master_unavailable"):
            create_master_link_token(session, owner_user_id=admin.id)


def test_invalid_and_revoked_tokens_are_safe(create_user):
    master = create_user(telegram_user_id=810000004)
    with get_session_factory()() as session:
        _profile(session, master, "Мастер Б")
        link = create_master_link_token(session, owner_user_id=master.id)
        session.commit()
        with pytest.raises(ClientBindingError, match="invalid_master_link"):
            resolve_start_token(session, start_token="missing", telegram_user_id=910000004)
        revoke_master_link_token(session, token=link.token)
        session.commit()
        with pytest.raises(ClientBindingError, match="invalid_master_link"):
            resolve_start_token(
                session,
                start_token=link.token,
                telegram_user_id=910000004,
            )


def test_multi_binding_keeps_owner_relationships_isolated(create_user):
    master_a = create_user(telegram_user_id=810000005)
    master_b = create_user(telegram_user_id=810000006)
    client_telegram_id = 910000005
    with get_session_factory()() as session:
        _profile(session, master_a, "Мастер А")
        _profile(session, master_b, "Мастер Б")
        session.add_all(
            [
                ClientTelegramIdentity(
                    owner_user_id=master_a.id,
                    telegram_user_id=client_telegram_id,
                    status="pending",
                    requested_public_name="Клиентка",
                ),
                ClientTelegramIdentity(
                    owner_user_id=master_b.id,
                    telegram_user_id=client_telegram_id,
                    status="pending",
                    requested_public_name="Клиентка",
                ),
            ]
        )
        session.commit()
        masters = list_client_masters(session, telegram_user_id=client_telegram_id)
        assert [master.display_name for master in masters] == ["Мастер А", "Мастер Б"]


def test_same_owner_and_client_telegram_pair_remains_unique(create_user):
    master = create_user(telegram_user_id=810000007)
    with get_session_factory()() as session:
        session.add_all(
            [
                ClientTelegramIdentity(
                    owner_user_id=master.id,
                    telegram_user_id=910000007,
                    status="pending",
                    requested_public_name="Одна",
                ),
                ClientTelegramIdentity(
                    owner_user_id=master.id,
                    telegram_user_id=910000007,
                    status="pending",
                    requested_public_name="Другая",
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()
