from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from app.auth import ClientTransportIdentity
from app.client_models import BookingRequest, MasterPublicProfile
from app.db import get_session_factory
from app.models import Service
from app.services.client_binding import create_master_link_token
from app.services.client_booking_draft_submit import submit_booking_draft_idempotent
from app.services.client_booking_drafts import (
    create_booking_draft,
    draft_slots,
    select_booking_draft_slot,
    update_booking_draft_composition,
)
from app.services.client_booking_requests import (
    MAX_PENDING_REQUESTS_PER_BINDING,
    create_client_booking_request,
)
from app.services.client_contour import require_client_binding
from app.services.normalization import normalize_public_name
from app.services.scheduling_common import SchedulingDomainError


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
            "X-Request-ID": "guard-start",
        },
        json={"start_token": token, "requested_public_name": "Анна"},
    )
    assert response.status_code == 200
    return response.json()["master"]["binding_id"]


def test_draft_is_single_submit_and_cannot_be_mutated_after_submit(
    client,
    create_user,
    create_availability,
):
    master = create_user(telegram_user_id=890000001)
    _service(master.id)
    day = date.today() + timedelta(days=40)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(18))
    binding_id = _binding(client, master, 990000001)
    identity = ClientTransportIdentity(telegram_user_id=990000001, request_id="draft")

    with get_session_factory()() as session:
        context = require_client_binding(session, identity, binding_id=binding_id)
        draft = create_booking_draft(session, context, "Маникюр")
        draft_id = draft.draft_id
        slots = draft_slots(session, context, draft_id, day).starts_at
        assert slots
        select_booking_draft_slot(session, context, draft_id, slots[0])
        first = submit_booking_draft_idempotent(session, identity, context, draft_id)
        first_id = first.id

    with get_session_factory()() as session:
        context = require_client_binding(session, identity, binding_id=binding_id)
        second = submit_booking_draft_idempotent(session, identity, context, draft_id)
        assert second.id == first_id
        try:
            update_booking_draft_composition(
                session,
                context,
                draft_id,
                addon_names=[],
                addon_quantities={},
            )
        except SchedulingDomainError as exc:
            assert exc.code == "client_booking_draft_submitted"
        else:
            raise AssertionError("submitted draft must be immutable")
        rows = (
            session.query(BookingRequest)
            .filter(BookingRequest.source_draft_id == draft_id)
            .all()
        )
        assert len(rows) == 1


def test_pending_request_limit_counts_only_pending(
    client,
    create_user,
    create_availability,
):
    master = create_user(telegram_user_id=890000002)
    _service(master.id)
    day = date.today() + timedelta(days=41)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(20))
    binding_id = _binding(client, master, 990000002)
    identity = ClientTransportIdentity(telegram_user_id=990000002, request_id="pending")

    with get_session_factory()() as session:
        context = require_client_binding(session, identity, binding_id=binding_id)
        created = []
        for index in range(MAX_PENDING_REQUESTS_PER_BINDING):
            created.append(
                create_client_booking_request(
                    session,
                    identity,
                    context,
                    service_name="Маникюр",
                    addon_names=[],
                    addon_quantities={},
                    starts_at=datetime.combine(
                        day,
                        time(10 + index * 2),
                        tzinfo=UTC,
                    ),
                    idempotency_key=f"pending-{index}",
                )
            )
        assert len(created) == MAX_PENDING_REQUESTS_PER_BINDING

    with get_session_factory()() as session:
        context = require_client_binding(session, identity, binding_id=binding_id)
        try:
            create_client_booking_request(
                session,
                identity,
                context,
                service_name="Маникюр",
                addon_names=[],
                addon_quantities={},
                starts_at=datetime.combine(day, time(18), tzinfo=UTC),
                idempotency_key="pending-over-limit",
            )
        except SchedulingDomainError as exc:
            assert exc.code == "client_pending_request_limit"
            assert exc.status_code == 429
        else:
            raise AssertionError("pending limit must reject excess requests")

    with get_session_factory()() as session:
        first = session.get(BookingRequest, created[0].id)
        first.status = "cancelled"
        session.commit()
    with get_session_factory()() as session:
        context = require_client_binding(session, identity, binding_id=binding_id)
        replacement = create_client_booking_request(
            session,
            identity,
            context,
            service_name="Маникюр",
            addon_names=[],
            addon_quantities={},
            starts_at=datetime.combine(day, time(18), tzinfo=UTC),
            idempotency_key="pending-after-cancel",
        )
        assert replacement.status == "pending"


def test_backend_application_has_no_client_telegram_bot_token_reference():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    server_roots = [app_dir / "api", app_dir / "services"]
    server_files = [
        app_dir / "main.py",
        app_dir / "client_models.py",
        app_dir / "client_notification_models.py",
    ]
    offenders: list[str] = []
    for root in server_roots:
        for path in root.rglob("*.py"):
            if "CLIENT_TELEGRAM_BOT_TOKEN" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(app_dir)))
    for path in server_files:
        if "CLIENT_TELEGRAM_BOT_TOKEN" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(app_dir)))
    assert offenders == []
