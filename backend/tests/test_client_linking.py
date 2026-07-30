from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.auth import ClientTransportIdentity, RequestIdentity
from app.client_models import BookingRequest, ClientTelegramIdentity, MasterPublicProfile
from app.client_notification_models import ClientLinkRecord, ClientPersonalLinkToken
from app.db import get_session_factory
from app.models import Client, ClientProfileStatus, UserRole
from app.services.client_binding import create_master_link_token
from app.services.client_linking import (
    confirm_telegram_contact,
    consume_personal_client_link,
    create_personal_client_link,
    set_manual_phone_hint,
    undo_client_link,
)
from app.services.normalization import normalize_public_name
from app.services.web_client_linking import booking_request_phone_preselect


def _client(owner_id, name: str, phone: str) -> Client:
    with get_session_factory()() as session:
        row = Client(
            owner_user_id=owner_id,
            public_name=name,
            normalized_public_name=normalize_public_name(name),
            phone=phone,
            profile_status=ClientProfileStatus.active,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row


def _binding(client, master, telegram_user_id: int, name: str = "Анна"):
    with get_session_factory()() as session:
        session.add(MasterPublicProfile(owner_user_id=master.id, display_name="Мастер"))
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()
    response = client.post(
        "/api/v1/client/start",
        headers={
            "X-Nails-Client-Internal-Key": "c" * 64,
            "X-Telegram-User-ID": str(telegram_user_id),
            "X-Request-ID": "link-start",
        },
        json={"start_token": token, "requested_public_name": name},
    )
    assert response.status_code == 200
    return response.json()["master"]["binding_id"]


def test_confirmed_contact_links_exact_single_owner_scoped_match(client, create_user):
    master = create_user(telegram_user_id=880000001)
    other_master = create_user(telegram_user_id=880000002)
    target = _client(master.id, "Анна Карточка", "+7 (999) 111-22-33")
    _client(other_master.id, "Чужая", "+7 999 111 22 33")
    binding_id = _binding(client, master, 980000001)

    with get_session_factory()() as session:
        result = confirm_telegram_contact(
            session,
            ClientTransportIdentity(telegram_user_id=980000001, request_id="confirmed"),
            binding_id=binding_id,
            contact_user_id=980000001,
            phone_number="8 999 111 22 33",
        )
        assert result.linked is True
        binding = session.get(ClientTelegramIdentity, binding_id)
        assert binding.client_id == target.id
        assert binding.status == "active"
        record = session.scalar(
            select(ClientLinkRecord).where(ClientLinkRecord.binding_id == binding_id)
        )
        assert record is not None
        assert record.source == "confirmed_contact"


def test_confirmed_contact_ambiguous_does_not_link(client, create_user):
    master = create_user(telegram_user_id=880000003)
    _client(master.id, "Анна Один", "+7 999 222 33 44")
    _client(master.id, "Анна Два", "8 (999) 222-33-44")
    binding_id = _binding(client, master, 980000003)

    with get_session_factory()() as session:
        result = confirm_telegram_contact(
            session,
            ClientTransportIdentity(telegram_user_id=980000003, request_id="confirmed"),
            binding_id=binding_id,
            contact_user_id=980000003,
            phone_number="+7 999 222 33 44",
        )
        assert result.linked is False
        assert result.result == "ambiguous"
        binding = session.get(ClientTelegramIdentity, binding_id)
        assert binding.client_id is None
        assert binding.status == "pending"


def test_foreign_telegram_contact_is_rejected(client, create_user):
    master = create_user(telegram_user_id=880000004)
    _client(master.id, "Анна", "+7 999 333 44 55")
    binding_id = _binding(client, master, 980000004)

    with get_session_factory()() as session:
        try:
            confirm_telegram_contact(
                session,
                ClientTransportIdentity(telegram_user_id=980000004, request_id="foreign"),
                binding_id=binding_id,
                contact_user_id=123456789,
                phone_number="+7 999 333 44 55",
            )
        except Exception as exc:
            assert getattr(exc, "code", None) == "telegram_contact_identity_mismatch"
        else:
            raise AssertionError("foreign Telegram contact must be rejected")
        binding = session.get(ClientTelegramIdentity, binding_id)
        assert binding.client_id is None


def test_manual_phone_is_hint_only_and_preselect_visible_only_to_master(
    client,
    create_user,
):
    master = create_user(telegram_user_id=880000005)
    card = _client(master.id, "Карточка", "+7 999 444 55 66")
    binding_id = _binding(client, master, 980000005, "Совсем другое имя")

    with get_session_factory()() as session:
        result = set_manual_phone_hint(
            session,
            ClientTransportIdentity(telegram_user_id=980000005, request_id="hint"),
            binding_id=binding_id,
            phone_number="8 999 444 55 66",
        )
        assert result.accepted
        binding = session.get(ClientTelegramIdentity, binding_id)
        assert binding.client_id is None
        assert binding.status == "pending"

        request = BookingRequest(
            owner_user_id=master.id,
            binding_id=binding.id,
            client_id=None,
            requested_public_name=binding.requested_public_name,
            service_name="Тест",
            addon_names=[],
            addon_quantities={},
            starts_at=datetime.now(UTC),
            status="pending",
            idempotency_key="hint-preselect",
        )
        session.add(request)
        session.commit()
        request_id = request.id

    with get_session_factory()() as session:
        preselect = booking_request_phone_preselect(
            session,
            RequestIdentity(
                user_id=master.id,
                telegram_user_id=master.telegram_user_id,
                role=UserRole.master,
                request_id="preselect",
            ),
            booking_request_id=request_id,
        )
        assert preselect.client_id == card.id
        assert preselect.reason
        binding = session.get(ClientTelegramIdentity, binding_id)
        assert binding.client_id is None
        assert binding.status == "pending"


def test_name_never_preselects_without_phone(client, create_user):
    master = create_user(telegram_user_id=880000006)
    _client(master.id, "Анна", "+7 999 555 66 77")
    binding_id = _binding(client, master, 980000006, "Анна")
    with get_session_factory()() as session:
        binding = session.get(ClientTelegramIdentity, binding_id)
        request = BookingRequest(
            owner_user_id=master.id,
            binding_id=binding.id,
            requested_public_name="Анна",
            service_name="Тест",
            addon_names=[],
            addon_quantities={},
            starts_at=datetime.now(UTC),
            status="pending",
            idempotency_key="name-no-preselect",
        )
        session.add(request)
        session.commit()
        request_id = request.id
    with get_session_factory()() as session:
        preselect = booking_request_phone_preselect(
            session,
            RequestIdentity(
                user_id=master.id,
                telegram_user_id=master.telegram_user_id,
                role=UserRole.master,
                request_id="preselect",
            ),
            booking_request_id=request_id,
        )
        assert preselect.client_id is None


def test_personal_link_is_one_time_revocable_and_undoable(client, create_user):
    master = create_user(telegram_user_id=880000007)
    target = _client(master.id, "Анна", "+7 999 666 77 88")
    identity = RequestIdentity(
        user_id=master.id,
        telegram_user_id=master.telegram_user_id,
        role=UserRole.master,
        request_id="personal",
    )
    with get_session_factory()() as session:
        created = create_personal_client_link(session, identity, client_id=target.id)
        token = created.token

    with get_session_factory()() as session:
        _, binding = consume_personal_client_link(
            session,
            ClientTransportIdentity(telegram_user_id=980000007, request_id="consume"),
            token=token,
            requested_public_name="Анна",
        )
        binding_id = binding.id
        record = session.scalar(
            select(ClientLinkRecord).where(ClientLinkRecord.binding_id == binding_id)
        )
        record_id = record.id
        stored_token = session.get(ClientPersonalLinkToken, token)
        assert stored_token.consumed_at is not None

    with get_session_factory()() as session:
        try:
            consume_personal_client_link(
                session,
                ClientTransportIdentity(telegram_user_id=980000008, request_id="steal"),
                token=token,
                requested_public_name="Мария",
            )
        except Exception as exc:
            assert getattr(exc, "code", None) == "invalid_client_personal_link"
        else:
            raise AssertionError("used personal link must be one-time")

    with get_session_factory()() as session:
        undone = undo_client_link(session, identity, link_record_id=record_id)
        assert undone.changed
        binding = session.get(ClientTelegramIdentity, binding_id)
        assert binding.client_id is None
        assert binding.status == "pending"
