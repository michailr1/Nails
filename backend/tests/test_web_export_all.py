from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from conftest import WEB_ORIGIN_HEADERS
from openpyxl import load_workbook
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.models import AuditEvent, Booking, BookingStatus, Client, ClientProfileStatus, Service
from app.services.normalization import normalize_public_name
from app.services.web_auth import _keyed_hash
from app.web_auth_models import WebSession


def _authenticate(client, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    token = "all-export-session-" + str(user_id)
    settings = get_settings()
    with get_session_factory()() as session:
        session.add(
            WebSession(
                token_hash=_keyed_hash(
                    token,
                    purpose="session-token",
                    settings=settings,
                ),
                user_id=user_id,
                last_seen_at=now,
                idle_expires_at=now + timedelta(hours=1),
                absolute_expires_at=now + timedelta(days=1),
                rotation_counter=1,
                created_ip_hash="b" * 64,
                last_ip_hash="b" * 64,
                request_id="web-all-export-test",
            )
        )
        session.commit()
    client.cookies.set("__Host-nails_session", token)


def _seed_booking(owner_user_id: uuid.UUID, *, suffix: str, day: int) -> None:
    starts_at = datetime(2026, 6, day, 9, 0, tzinfo=UTC)
    with get_session_factory()() as session:
        customer = Client(
            owner_user_id=owner_user_id,
            public_name=f"Клиентка {suffix}",
            normalized_public_name=normalize_public_name(f"Клиентка {suffix}"),
            profile_status=ClientProfileStatus.active,
        )
        service = Service(
            owner_user_id=owner_user_id,
            public_name=f"Услуга {suffix}",
            normalized_public_name=normalize_public_name(f"Услуга {suffix}"),
            price_amount=Decimal("1900.00"),
            currency="RUB",
            duration_minutes=90,
            buffer_before_minutes=0,
            buffer_after_minutes=10,
            is_active=True,
        )
        session.add_all([customer, service])
        session.flush()
        session.add(
            Booking(
                owner_user_id=owner_user_id,
                client_id=customer.id,
                service_id=service.id,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(minutes=90),
                reserved_starts_at=starts_at,
                reserved_ends_at=starts_at + timedelta(minutes=100),
                duration_minutes_snapshot=90,
                buffer_before_minutes_snapshot=0,
                buffer_after_minutes_snapshot=10,
                status=BookingStatus.scheduled,
                price_amount=Decimal("1900.00"),
                currency="RUB",
                price_source="service_snapshot",
                idempotency_key=f"all-export-{suffix}",
            )
        )
        session.commit()


def test_full_calendar_export_is_owner_scoped_and_audited(client, create_user):
    owner = create_user(telegram_user_id=200000001)
    other = create_user(telegram_user_id=200000002)
    _seed_booking(owner.id, suffix="owner-old", day=2)
    _seed_booking(owner.id, suffix="owner-new", day=28)
    _seed_booking(other.id, suffix="other", day=15)
    _authenticate(client, owner.id)

    response = client.post(
        "/web/api/exports/calendar/all",
        headers=WEB_ORIGIN_HEADERS,
        params={"format": "xlsx"},
    )

    assert response.status_code == 200
    assert "calendar-all-" in response.headers["content-disposition"]
    workbook = load_workbook(io.BytesIO(response.content), read_only=True)
    worksheet = workbook["Весь календарь"]
    values = list(worksheet.values)
    assert len(values) == 3
    flattened = " ".join(str(value) for row in values for value in row if value is not None)
    assert "Клиентка owner-old" in flattened
    assert "Клиентка owner-new" in flattened
    assert "Клиентка other" not in flattened

    with get_session_factory()() as session:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.object_type == "calendar_all")
        )
        assert event is not None
        assert event.owner_user_id == owner.id
        assert event.safe_changes == {"format": "xlsx", "row_count": 2}
