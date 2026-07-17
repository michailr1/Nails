from collections.abc import Callable
from datetime import date, time

import pytest
from fastapi.testclient import TestClient

from app.db import get_session_factory
from app.models import AuditEvent
from app.services import scheduling_dates


@pytest.mark.usefixtures("clean_database")
def test_date_resolver_uses_backend_calendar_not_model_arithmetic(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_user()
    monkeypatch.setattr(scheduling_dates, "_local_today", lambda: date(2026, 7, 13))

    cases = (
        (
            {"kind": "weekday", "weekday_iso": 5, "occurrence": "nearest_future"},
            "2026-07-17",
            5,
        ),
        (
            {"kind": "weekday", "weekday_iso": 5, "occurrence": "next_week"},
            "2026-07-24",
            5,
        ),
        (
            {
                "kind": "month_day",
                "month": 7,
                "day_of_month": 18,
                "occurrence": "nearest_future",
            },
            "2026-07-18",
            6,
        ),
        ({"kind": "relative_days", "offset_days": 1}, "2026-07-14", 2),
        ({"kind": "absolute", "day": "2026-07-18"}, "2026-07-18", 6),
    )

    for payload, expected_day, expected_weekday in cases:
        response = client.post(
            "/api/v1/scheduling/date/resolve",
            headers=auth_headers(),
            json=payload,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["today"] == "2026-07-13"
        assert body["today_weekday_iso"] == 1
        assert body["day"] == expected_day
        assert body["weekday_iso"] == expected_weekday
        assert body["timezone"] == "Europe/Berlin"


@pytest.mark.usefixtures("clean_database")
def test_month_day_resolver_rolls_forward_year_and_handles_leap_day(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_user()
    monkeypatch.setattr(scheduling_dates, "_local_today", lambda: date(2026, 12, 31))

    july = client.post(
        "/api/v1/scheduling/date/resolve",
        headers=auth_headers(),
        json={
            "kind": "month_day",
            "month": 7,
            "day_of_month": 18,
            "occurrence": "nearest_future",
        },
    )
    assert july.status_code == 200, july.text
    assert july.json()["day"] == "2027-07-18"

    leap = client.post(
        "/api/v1/scheduling/date/resolve",
        headers=auth_headers(),
        json={
            "kind": "month_day",
            "month": 2,
            "day_of_month": 29,
            "occurrence": "nearest_future",
        },
    )
    assert leap.status_code == 200, leap.text
    assert leap.json()["day"] == "2028-02-29"
    assert leap.json()["weekday_iso"] == date(2028, 2, 29).isoweekday()


@pytest.mark.usefixtures("clean_database")
def test_schedule_can_be_corrected_without_restarting_onboarding(
    client: TestClient,
    create_user: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    for work_day in (date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 18)):
        create_availability(
            user.id,
            day=work_day,
            start_time=time(11, 0),
            end_time=time(20, 0) if work_day != date(2026, 7, 18) else time(15, 0),
        )

    payload = {
        "days": [
            {
                "day": "2026-07-17",
                "state": "available",
                "intervals": [{"start_time": "11:00", "end_time": "15:00"}],
            },
            {
                "day": "2026-07-18",
                "state": "unknown",
                "intervals": [],
            },
        ]
    }
    response = client.put(
        "/api/v1/scheduling/availability",
        headers=auth_headers(request_id="correct-schedule"),
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "days": [
            {
                "day": "2026-07-17",
                "weekday_iso": 5,
                "availability_known": True,
                "availability": [
                    {
                        "start_time": "11:00:00",
                        "end_time": "15:00:00",
                        "is_available": True,
                        "note": None,
                    }
                ],
                "changed": True,
            },
            {
                "day": "2026-07-18",
                "weekday_iso": 6,
                "availability_known": False,
                "availability": [],
                "changed": True,
            },
        ]
    }

    for untouched in ("2026-07-14", "2026-07-15"):
        day_view = client.get(
            "/api/v1/scheduling/day",
            headers=auth_headers(),
            params={"day": untouched},
        )
        assert day_view.status_code == 200, day_view.text
        assert day_view.json()["availability_known"] is True

    repeated = client.put(
        "/api/v1/scheduling/availability",
        headers=auth_headers(request_id="correct-schedule-repeat"),
        json=payload,
    )
    assert repeated.status_code == 200, repeated.text
    assert [item["changed"] for item in repeated.json()["days"]] == [False, False]

    with get_session_factory()() as session:
        audit = session.query(AuditEvent).filter_by(action="availability.replaced").all()
        assert len(audit) == 2
        assert {item.safe_changes["day"] for item in audit} == {
            "2026-07-17",
            "2026-07-18",
        }


@pytest.mark.usefixtures("clean_database")
def test_suggestion_window_change_does_not_displace_existing_booking(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id)
    create_availability(
        user.id,
        day=date(2026, 7, 17),
        start_time=time(11, 0),
        end_time=time(20, 0),
    )
    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(),
        json={"public_name": "Анна", "phone": None},
    )
    assert created_client.status_code == 200, created_client.text

    booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="booking-before-schedule-change"),
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "starts_at": "2026-07-17T12:00:00+02:00",
            "idempotency_key": "test-schedule-window-change",
        },
    )
    assert booking.status_code == 200, booking.text

    response = client.put(
        "/api/v1/scheduling/availability",
        headers=auth_headers(request_id="suggestion-window-change"),
        json={
            "days": [
                {
                    "day": "2026-07-17",
                    "state": "available",
                    "intervals": [{"start_time": "11:00", "end_time": "13:00"}],
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["days"][0]["changed"] is True
    assert response.json()["days"][0]["availability"][0]["end_time"] == "13:00:00"


@pytest.mark.usefixtures("clean_database")
def test_day_off_change_cannot_displace_existing_booking(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    create_availability: Callable,
    auth_headers: Callable,
) -> None:
    user = create_user()
    create_service(user.id)
    create_availability(
        user.id,
        day=date(2026, 7, 17),
        start_time=time(11, 0),
        end_time=time(20, 0),
    )
    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(),
        json={"public_name": "Анна", "phone": None},
    )
    assert created_client.status_code == 200, created_client.text
    booking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id="booking-before-day-off"),
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "starts_at": "2026-07-17T12:00:00+02:00",
            "idempotency_key": "test-day-off-conflict",
        },
    )
    assert booking.status_code == 200, booking.text

    response = client.put(
        "/api/v1/scheduling/availability",
        headers=auth_headers(request_id="conflicting-day-off-change"),
        json={
            "days": [
                {
                    "day": "2026-07-17",
                    "state": "unavailable",
                    "intervals": [],
                    "note": "Выходной",
                }
            ]
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {
        "code": "availability_conflicts_with_bookings",
        "details": {"day": "2026-07-17", "booking_count": 1},
    }

    day_view = client.get(
        "/api/v1/scheduling/day",
        headers=auth_headers(),
        params={"day": "2026-07-17"},
    )
    assert day_view.status_code == 200, day_view.text
    assert day_view.json()["availability"][0]["end_time"] == "20:00:00"
