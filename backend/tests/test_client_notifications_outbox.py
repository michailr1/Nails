from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.auth import ClientTransportIdentity, RequestIdentity
from app.client_models import (
    BookingRequestStatus,
    ClientTelegramIdentity,
    MasterPublicProfile,
)
from app.client_notification_models import ClientNotificationOutbox
from app.db import get_session_factory
from app.models import Service, UserRole
from app.schemas.client_booking_requests import BookingRequestResolutionValue
from app.services.client_binding import create_master_link_token
from app.services.client_booking_requests import (
    approve_master_booking_request,
    create_client_booking_request,
    reject_master_booking_request,
)
from app.services.client_contour import require_client_binding
from app.services.client_notifications import (
    acknowledge_client_notification,
    assert_safe_outbox_payload,
    claim_client_notification,
)
from app.services.normalization import normalize_public_name


def _service(owner_id, name: str = "Маникюр") -> None:
    with get_session_factory()() as session:
        session.add(
            Service(
                owner_user_id=owner_id,
                public_name=name,
                normalized_public_name=normalize_public_name(name),
                price_amount=Decimal("2500"),
                currency="RUB",
                duration_minutes=60,
                buffer_before_minutes=0,
                buffer_after_minutes=0,
                is_active=True,
                kind="base",
                price_type="fixed",
                extra_minutes=0,
            )
        )
        session.commit()


def _binding(client, master, telegram_user_id: int):
    with get_session_factory()() as session:
        session.add(MasterPublicProfile(owner_user_id=master.id, display_name="Мастер"))
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()
    response = client.post(
        "/api/v1/client/start",
        headers={
            "X-Nails-Client-Internal-Key": "c" * 64,
            "X-Telegram-User-ID": str(telegram_user_id),
            "X-Request-ID": "outbox-start",
        },
        json={"start_token": token, "requested_public_name": "Анна"},
    )
    assert response.status_code == 200
    return response.json()["master"]["binding_id"]


def test_reject_enqueues_safe_outbox_and_ack_updates_reachability(
    client,
    create_user,
    create_availability,
):
    master = create_user(telegram_user_id=870000001)
    _service(master.id)
    day = date.today() + timedelta(days=21)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(18))
    binding_id = _binding(client, master, 970000001)

    with get_session_factory()() as session:
        context = require_client_binding(
            session,
            ClientTransportIdentity(telegram_user_id=970000001, request_id="create"),
            binding_id=binding_id,
        )
        request = create_client_booking_request(
            session,
            ClientTransportIdentity(telegram_user_id=970000001, request_id="create"),
            context,
            service_name="Маникюр",
            addon_names=[],
            addon_quantities={},
            starts_at=datetime.combine(day, time(11), tzinfo=UTC),
            idempotency_key="outbox-1",
        )
        request_id = request.id

    with get_session_factory()() as session:
        rejected = reject_master_booking_request(
            session,
            RequestIdentity(
                user_id=master.id,
                telegram_user_id=master.telegram_user_id,
                role=UserRole.master,
                request_id="reject",
            ),
            request_id,
        )
        assert rejected.status == BookingRequestStatus.rejected
        rows = session.scalars(select(ClientNotificationOutbox)).all()
        assert len(rows) == 1
        assert rows[0].event_type == "rejected"
        assert assert_safe_outbox_payload(dict(rows[0].payload))
        serialized = str(rows[0].payload).casefold()
        assert "phone" not in serialized
        assert "note" not in serialized
        assert str(master.telegram_user_id) not in serialized

    with get_session_factory()() as session:
        claim = claim_client_notification(session)
        assert claim.claimed is True
        assert claim.telegram_user_id == 970000001
        ack = acknowledge_client_notification(
            session,
            claim_id=claim.claim_id,
            outcome="sent",
            error_code=None,
        )
        assert ack.status == "sent"
        binding = session.get(ClientTelegramIdentity, binding_id)
        assert binding.bot_reachability == "reachable"


def test_failed_delivery_retries_without_blocking_next_row(
    client,
    create_user,
    create_availability,
):
    master = create_user(telegram_user_id=870000002)
    _service(master.id)
    day = date.today() + timedelta(days=22)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(18))
    binding_id = _binding(client, master, 970000002)

    request_ids = []
    for index, hour in enumerate((11, 13)):
        with get_session_factory()() as session:
            context = require_client_binding(
                session,
                ClientTransportIdentity(telegram_user_id=970000002, request_id=f"c{index}"),
                binding_id=binding_id,
            )
            row = create_client_booking_request(
                session,
                ClientTransportIdentity(telegram_user_id=970000002, request_id=f"c{index}"),
                context,
                service_name="Маникюр",
                addon_names=[],
                addon_quantities={},
                starts_at=datetime.combine(day, time(hour), tzinfo=UTC),
                idempotency_key=f"outbox-retry-{index}",
            )
            request_ids.append(row.id)
        with get_session_factory()() as session:
            reject_master_booking_request(
                session,
                RequestIdentity(
                    user_id=master.id,
                    telegram_user_id=master.telegram_user_id,
                    role=UserRole.master,
                    request_id=f"r{index}",
                ),
                request_ids[-1],
            )

    with get_session_factory()() as session:
        first = claim_client_notification(session)
        assert first.claimed
        retry = acknowledge_client_notification(
            session,
            claim_id=first.claim_id,
            outcome="retry",
            error_code="timeout",
        )
        assert retry.status == "pending"

    with get_session_factory()() as session:
        second = claim_client_notification(session)
        assert second.claimed
        assert second.notification_id != first.notification_id


def test_approve_enqueues_once_on_idempotent_retry(
    client,
    create_user,
    create_availability,
):
    master = create_user(telegram_user_id=870000003)
    _service(master.id)
    day = date.today() + timedelta(days=23)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(18))
    binding_id = _binding(client, master, 970000003)

    with get_session_factory()() as session:
        context = require_client_binding(
            session,
            ClientTransportIdentity(telegram_user_id=970000003, request_id="create"),
            binding_id=binding_id,
        )
        row = create_client_booking_request(
            session,
            ClientTransportIdentity(telegram_user_id=970000003, request_id="create"),
            context,
            service_name="Маникюр",
            addon_names=[],
            addon_quantities={},
            starts_at=datetime.combine(day, time(12), tzinfo=UTC),
            idempotency_key="approve-outbox",
        )
        request_id = row.id

    identity = RequestIdentity(
        user_id=master.id,
        telegram_user_id=master.telegram_user_id,
        role=UserRole.master,
        request_id="approve",
    )
    with get_session_factory()() as session:
        first = approve_master_booking_request(
            session,
            identity,
            request_id,
            resolution=BookingRequestResolutionValue.create_new,
            selected_client_id=None,
        )
        assert first.status == BookingRequestStatus.approved
    with get_session_factory()() as session:
        second = approve_master_booking_request(
            session,
            identity,
            request_id,
            resolution=BookingRequestResolutionValue.create_new,
            selected_client_id=None,
        )
        assert second.id == request_id
        rows = session.scalars(
            select(ClientNotificationOutbox).where(
                ClientNotificationOutbox.booking_request_id == request_id
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].event_type == "approved"
