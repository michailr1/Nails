import uuid
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.db import get_session_factory
from app.models import Client
from app.services.normalization import normalize_public_name


def _create_client(owner_user_id, public_name: str = "Клиентка") -> None:
    with get_session_factory()() as session:
        session.add(
            Client(
                owner_user_id=owner_user_id,
                public_name=public_name,
                normalized_public_name=normalize_public_name(public_name),
                phone=None,
            )
        )
        session.commit()


def _booking_payload(day: date, hour: int, *, key: str) -> dict[str, str]:
    starts_at = datetime.combine(
        day,
        time(hour),
        tzinfo=ZoneInfo("Europe/Berlin"),
    )
    return {
        "client_public_name": "Клиентка",
        "service_name": "Маникюр",
        "starts_at": starts_at.isoformat(),
        "idempotency_key": key,
    }


def test_explicit_booking_succeeds_without_declared_hours(
    client,
    create_user,
    create_service,
    auth_headers,
):
    user = create_user()
    create_service(user.id)
    _create_client(user.id)
    day = date(2026, 7, 20)

    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(),
        json=_booking_payload(day, 16, key="open-default-16"),
    )

    assert response.status_code == 200
    assert response.json()["created"] is True
    assert response.json()["booking"]["starts_at"].startswith("2026-07-20T16:00:00")


def test_explicit_booking_outside_suggestion_window_still_succeeds(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    user = create_user()
    create_service(user.id)
    _create_client(user.id)
    day = date(2026, 7, 21)
    create_availability(user.id, day=day, start_time=time(11), end_time=time(20))

    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(),
        json=_booking_payload(day, 8, key="outside-suggestion-08"),
    )

    assert response.status_code == 200
    assert response.json()["created"] is True
    assert response.json()["booking"]["starts_at"].startswith("2026-07-21T08:00:00")


def test_explicit_booking_on_day_off_is_rejected_distinctly(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    user = create_user()
    create_service(user.id)
    _create_client(user.id)
    day = date(2026, 7, 22)
    create_availability(
        user.id,
        day=day,
        start_time=None,
        end_time=None,
        is_available=False,
        note="Выходной",
    )

    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(),
        json=_booking_payload(day, 16, key="day-off-16"),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "booking_on_day_off"


def test_free_slots_use_default_suggestion_window_when_hours_are_absent(
    client,
    create_user,
    create_service,
    auth_headers,
):
    user = create_user()
    create_service(
        user.id,
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    day = date(2026, 7, 23)

    response = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": day.isoformat(), "service_name": "Маникюр"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability_known"] is False
    assert payload["is_working"] is True
    assert payload["starts_at"][0].startswith("2026-07-23T10:00:00")
    assert payload["starts_at"][-1].startswith("2026-07-23T22:00:00")


def test_day_off_has_no_suggested_slots(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    user = create_user()
    create_service(user.id, duration_minutes=60, buffer_after_minutes=0)
    day = date(2026, 7, 24)
    create_availability(
        user.id,
        day=day,
        start_time=None,
        end_time=None,
        is_available=False,
    )

    response = client.get(
        "/api/v1/scheduling/slots",
        headers=auth_headers(),
        params={"day": day.isoformat(), "service_name": "Маникюр"},
    )

    assert response.status_code == 200
    assert response.json()["is_working"] is False
    assert response.json()["starts_at"] == []


def test_positive_window_change_does_not_conflict_with_existing_booking(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    user = create_user()
    create_service(user.id, duration_minutes=60, buffer_after_minutes=0)
    _create_client(user.id)
    day = date(2026, 7, 25)
    create_availability(user.id, day=day, start_time=time(11), end_time=time(20))

    booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(),
        json=_booking_payload(day, 8, key=f"positive-window-{uuid.uuid4()}"),
    )
    assert booking.status_code == 200

    preview = client.post(
        "/api/v1/scheduling/availability/preview",
        headers=auth_headers(),
        json={
            "days": [
                {
                    "day": day.isoformat(),
                    "state": "available",
                    "intervals": [{"start_time": "12:00", "end_time": "18:00"}],
                }
            ]
        },
    )

    assert preview.status_code == 200
    assert preview.json()["days"][0]["can_apply"] is True
    assert preview.json()["days"][0]["conflicts"] == []
