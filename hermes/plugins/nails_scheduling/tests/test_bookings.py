import json

import pytest
from nails_scheduling import operations, tools, verified_operations


def _set_context(monkeypatch, *, platform="telegram", user_id="700000001"):
    values = {
        "HERMES_SESSION_PLATFORM": platform,
        "HERMES_SESSION_USER_ID": user_id,
    }
    monkeypatch.setattr(
        tools,
        "_get_session_env",
        lambda name, default="": values.get(name, default),
    )


def _set_key(monkeypatch, value="k" * 64):
    monkeypatch.setenv("NAILS_INTERNAL_API_KEY", value)


def _booking_payload(
    *,
    client="Анна",
    service="Маникюр",
    starts_at="2026-07-18T13:10:00+02:00",
):
    return {
        "id": "22222222-2222-4222-8222-222222222222",
        "client_public_name": client,
        "service_name": service,
        "starts_at": starts_at,
        "ends_at": "2026-07-18T15:10:00+02:00",
        "reserved_starts_at": starts_at,
        "reserved_ends_at": "2026-07-18T15:31:00+02:00",
        "status": "scheduled",
        "price_amount": "2500.00",
        "currency": "RUB",
        "duration_minutes": 120,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 21,
    }


def _day_payload(*, bookings=None):
    return {
        "day": "2026-07-18",
        "timezone": "Europe/Berlin",
        "weekday_iso": 6,
        "availability_known": False,
        "availability": [],
        "bookings": bookings if bookings is not None else [],
    }


def _exact_client_response():
    return {
        "ok": True,
        "action": "find_client",
        "result": {
            "found": True,
            "client": {"public_name": "Анна", "phone": None},
        },
    }


def test_create_booking_accepts_exact_time_and_returns_verified_readback(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["path"].endswith("/exact"):
            return _exact_client_response()
        if kwargs["path"].endswith("/day"):
            return {
                "ok": True,
                "action": "day_view",
                "result": _day_payload(bookings=[_booking_payload()])
                if len([call for call in calls if call["path"].endswith("/day")]) > 1
                else _day_payload(),
            }
        if kwargs["path"].endswith("/bookings"):
            return {
                "ok": True,
                "action": "create_booking",
                "result": {"booking": _booking_payload(), "created": True},
            }
        pytest.fail(f"unexpected backend path: {kwargs['path']}")

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    monkeypatch.setattr(verified_operations, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "create_booking",
                "client_public_name": "Анна",
                "service_name": "Маникюр",
                "day": "2026-07-18",
                "start_time": "13:10",
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["result"]["created"] is True
    assert result["result"]["verified"] is True
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/clients/exact",
        "/api/v1/scheduling/day",
        "/api/v1/scheduling/bookings",
        "/api/v1/scheduling/day",
    ]
    body = calls[2]["json_body"]
    assert body["starts_at"] == "2026-07-18T13:10:00+02:00"
    assert set(body) == {"client_public_name", "service_name", "starts_at"}
    assert "idempotency_key" not in json.dumps(result)
    assert "id" not in result["result"]["booking"]


def test_duplicate_booking_is_detected_from_day_view_without_post(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["path"].endswith("/exact"):
            return _exact_client_response()
        if kwargs["path"].endswith("/day"):
            return {
                "ok": True,
                "action": "day_view",
                "result": _day_payload(bookings=[_booking_payload()]),
            }
        pytest.fail("booking POST must not be called")

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    monkeypatch.setattr(verified_operations, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "create_booking",
                "client_public_name": "Анна",
                "service_name": "Маникюр",
                "day": "2026-07-18",
                "start_time": "13:10",
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["result"]["created"] is False
    assert result["result"]["verified"] is True
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/clients/exact",
        "/api/v1/scheduling/day",
        "/api/v1/scheduling/day",
    ]


@pytest.mark.parametrize("backend_code", ["booking_on_day_off", "booking_overlap"])
def test_create_booking_preserves_authoritative_backend_rejection(monkeypatch, backend_code):
    _set_context(monkeypatch)
    _set_key(monkeypatch)

    def fake_call_backend(**kwargs):
        if kwargs["path"].endswith("/exact"):
            return _exact_client_response()
        if kwargs["path"].endswith("/day"):
            return {"ok": True, "action": "day_view", "result": _day_payload()}
        if kwargs["path"].endswith("/bookings"):
            return {
                "ok": False,
                "action": "create_booking",
                "error": {"code": backend_code, "message": "rejected"},
            }
        pytest.fail(f"unexpected backend path: {kwargs['path']}")

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    monkeypatch.setattr(verified_operations, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "create_booking",
                "client_public_name": "Анна",
                "service_name": "Маникюр",
                "day": "2026-07-18",
                "start_time": "08:07",
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == backend_code


def test_create_booking_requires_existing_exact_client(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["path"].endswith("/exact"):
            return {
                "ok": True,
                "action": "find_client",
                "result": {"found": False, "client": None},
            }
        pytest.fail("day view and booking must not be called")

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    monkeypatch.setattr(verified_operations, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "create_booking",
                "client_public_name": "Анна",
                "service_name": "Маникюр",
                "day": "2026-07-18",
                "start_time": "13:00",
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "client_not_found"
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/clients/exact"
    ]
