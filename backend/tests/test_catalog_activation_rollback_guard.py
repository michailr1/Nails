import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db import get_session_factory
from app.models import Client, Service


@pytest.mark.usefixtures("clean_database")
def test_previous_release_cannot_book_non_fixed_service(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    headers = auth_headers(request_id="rollback-guard-setup")

    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=headers,
        json={"public_name": "Анна"},
    )
    assert created_client.status_code == 200, created_client.text

    created_service = client.post(
        "/api/v1/scheduling/services",
        headers=headers,
        json={
            "public_name": "Маникюр",
            "price_type": "range",
            "price_min_amount": "2500.00",
            "price_max_amount": "3000.00",
            "duration_minutes": 120,
        },
    )
    assert created_service.status_code == 200, created_service.text

    starts_at = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=120)

    with get_session_factory()() as session:
        stored_client = session.scalar(
            select(Client).where(Client.owner_user_id == user.id)
        )
        service = session.scalar(
            select(Service).where(Service.owner_user_id == user.id)
        )
        assert stored_client is not None
        assert service is not None

        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    """
                    INSERT INTO bookings (
                        id,
                        owner_user_id,
                        client_id,
                        service_id,
                        starts_at,
                        ends_at,
                        expected_ends_at,
                        reserved_starts_at,
                        reserved_ends_at,
                        duration_minutes_snapshot,
                        buffer_before_minutes_snapshot,
                        buffer_after_minutes_snapshot,
                        status,
                        price_amount,
                        currency,
                        price_source,
                        idempotency_key
                    ) VALUES (
                        :id,
                        :owner_user_id,
                        :client_id,
                        :service_id,
                        :starts_at,
                        :ends_at,
                        :expected_ends_at,
                        :reserved_starts_at,
                        :reserved_ends_at,
                        :duration_minutes_snapshot,
                        0,
                        0,
                        'scheduled',
                        :price_amount,
                        'RUB',
                        'service_snapshot',
                        :idempotency_key
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "owner_user_id": user.id,
                    "client_id": stored_client.id,
                    "service_id": service.id,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "expected_ends_at": ends_at,
                    "reserved_starts_at": starts_at,
                    "reserved_ends_at": ends_at,
                    "duration_minutes_snapshot": 120,
                    "price_amount": Decimal("2500.00"),
                    "idempotency_key": "legacy-range-booking",
                },
            )
            session.flush()
