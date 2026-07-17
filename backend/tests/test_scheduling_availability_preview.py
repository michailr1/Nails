import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.db import get_session_factory
from app.models import Booking, BookingStatus, Client
from app.services.normalization import normalize_public_name


def test_preview_partial_day_is_read_only(
    client,
    create_user,
    create_availability,
    auth_headers,
):
    user = create_user()
    day = date(2026, 7, 18)
    create_availability(user.id, day=day, start_time=time(11), end_time=time(20))

    response = client.post(
        "/api/v1/scheduling/availability/preview",
        headers=auth_headers(),
        json={
            "days": [
                {
                    "day": day.isoformat(),
                    "state": "available",
                    "intervals": [
                        {"start_time": "11:00", "end_time": "13:00"},
                        {"start_time": "16:00", "end_time": "20:00"},
                    ],
                    "note": "Личные дела",
                }
            ]
        },
    )

    assert response.status_code == 200
    preview = response.json()["days"][0]
    assert preview["changed"] is True
    assert preview["can_apply"] is True
    assert preview["conflicts"] == []
    assert len(preview["current_availability"]) == 1
    assert len(preview["proposed_availability"]) == 2

    day_view = client.get(
        "/api/v1/scheduling/day",
        headers=auth_headers(),
        params={"day": day.isoformat()},
    )
    assert day_view.status_code == 200
    assert len(day_view.json()["availability"]) == 1
    assert day_view.json()["availability"][0]["start_time"] == "11:00:00"
    assert day_view.json()["availability"][0]["end_time"] == "20:00:00"


def test_preview_reports_booking_that_would_be_displaced(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    user = create_user()
    service = create_service(user.id, duration_minutes=120, buffer_after_minutes=20)
    day = date(2026, 7, 18)
    create_availability(user.id, day=day, start_time=time(11), end_time=time(20))

    timezone = ZoneInfo("Europe/Berlin")
    starts_at = datetime.combine(day, time(13), tzinfo=timezone).astimezone(UTC)
    ends_at = datetime.combine(day, time(15), tzinfo=timezone).astimezone(UTC)
    reserved_ends_at = datetime.combine(day, time(15, 20), tzinfo=timezone).astimezone(UTC)

    with get_session_factory()() as session:
        customer = Client(
            owner_user_id=user.id,
            public_name="Клиентка",
            normalized_public_name=normalize_public_name("Клиентка"),
            phone=None,
        )
        session.add(customer)
        session.flush()
        session.add(
            Booking(
                id=uuid.uuid4(),
                owner_user_id=user.id,
                client_id=customer.id,
                service_id=service.id,
                starts_at=starts_at,
                ends_at=ends_at,
                reserved_starts_at=starts_at,
                reserved_ends_at=reserved_ends_at,
                duration_minutes_snapshot=120,
                buffer_before_minutes_snapshot=0,
                buffer_after_minutes_snapshot=20,
                status=BookingStatus.scheduled,
                price_amount=Decimal("2500.00"),
                currency="RUB",
                price_source="service_snapshot",
                idempotency_key="preview-conflict-booking",
            )
        )
        session.commit()

    response = client.post(
        "/api/v1/scheduling/availability/preview",
        headers=auth_headers(),
        json={
            "days": [
                {
                    "day": day.isoformat(),
                    "state": "available",
                    "intervals": [
                        {"start_time": "11:00", "end_time": "13:00"},
                        {"start_time": "16:00", "end_time": "20:00"},
                    ],
                    "note": "Личные дела",
                }
            ]
        },
    )

    assert response.status_code == 200
    preview = response.json()["days"][0]
    assert preview["changed"] is True
    assert preview["can_apply"] is False
    assert len(preview["conflicts"]) == 1
    assert preview["conflicts"][0]["client_public_name"] == "Клиентка"
    assert preview["conflicts"][0]["service_name"] == "Маникюр"
