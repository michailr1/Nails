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


def _service_payload():
    return {
        "id": "11111111-1111-4111-8111-111111111111",
        "public_name": "Маникюр",
        "public_description": None,
        "price_amount": "2500.00",
        "currency": "RUB",
        "duration_minutes": 120,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 21,
    }


def _booking_payload(
    *,
    client="Анна",
    service="Маникюр",
    starts_at="2026-07-18T13:00:00+02:00",
):
    return {
        "id": "22222222-2222-4222-8222-222222222222",
        "client_public_name": client,
        "service_name": service,
        "starts_at": starts_at,
        "ends_at": "2026-07-18T15:00:00+02:00",
        "reserved_starts_at": starts_at,
        "reserved_ends_at": "2026-07-18T15:21:00+02:00",
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
        "availability_known": True,
        "availability": [],
        "bookings": bookings if bookings is not None else [],
    }


def _slots_payload(*, starts=None, known=True, working=True):
    return {
        "day": "2026-07-18",
        "timezone": "Europe/Berlin",
        "weekday_iso": 6,
        "availability_known": known,
        "is_working": working,
        "step_minutes": 15,
        "service": _service_payload(),
        "starts_at": (
            starts
            if starts is not None
            else ["2026-07-18T13:00:00+02:00"]
        ),
    }


def test_create_booking_checks_slot_and_returns_verified_readback(monkeypatch):
    _set_context(monkeypatch, user_id="700000001")
    _set_key(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["path"].endswith("/exact"):
            return {
                "ok": True,
                "action": "find_client",
                "result": {
                    "found": True,
                    "client": {"public_name": "Анна", "phone": None},
                },
            }
        if kwargs["path"].endswith("/slots"):
            return {"ok": True, "action": "free_slots", "result": _slots_payload()}
        if kwargs["path"].endswith("/day"):
            return {
                "ok": True,
                "action": "day_view",
                "result": _day_payload(bookings=[_booking_payload()]),
            }
        return {
            "ok": True,
            "action": "create_booking",
            "result": {"booking": _booking_payload(), "created": True},
        }

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    monkeypatch.setattr(verified_operations, "_call_backend", fake_call_backend)
    args = {
        "action": "create_booking",
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "day": "2026-07-18",
        "start_time": "13:00",
        "confirmed": True,
    }
    first = json.loads(tools.nails_scheduling(args))
    assert first["ok"] is True
    assert first["result"]["created"] is True
    assert first["result"]["verified"] is True
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/clients/exact",
        "/api/v1/scheduling/slots",
        "/api/v1/scheduling/bookings",
        "/api/v1/scheduling/day",
    ]
    body = calls[2]["json_body"]
    assert set(body) == {
        "client_public_name",
        "service_name",
        "starts_at",
    }
    assert body["starts_at"] == "2026-07-18T13:00:00+02:00"
    assert "idempotency_key" not in body
    assert "idempotency_key" not in json.dumps(first)
    assert "id" not in first["result"]["booking"]

    calls.clear()
    second = json.loads(tools.nails_scheduling(args))
    assert "idempotency_key" not in calls[2]["json_body"]
    assert second["ok"] is True
    assert second["result"]["verified"] is True


def test_duplicate_booking_is_detected_from_day_view_without_post(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["path"].endswith("/exact"):
            return {
                "ok": True,
                "action": "find_client",
                "result": {
                    "found": True,
                    "client": {"public_name": "Анна", "phone": None},
                },
            }
        if kwargs["path"].endswith("/slots"):
            return {"ok": True, "action": "free_slots", "result": _slots_payload(starts=[])}
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
                "start_time": "13:00",
                "confirmed": True,
            }
        )
    )
    assert result["ok"] is True
    assert result["result"]["created"] is False
    assert result["result"]["verified"] is True
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/clients/exact",
        "/api/v1/scheduling/slots",
        "/api/v1/scheduling/day",
        "/api/v1/scheduling/day",
    ]
    assert "id" not in result["result"]["booking"]


@pytest.mark.parametrize(
    ("slots", "start_time", "expected"),
    [
        (_slots_payload(starts=[], known=False), "13:00", "availability_unknown"),
        (_slots_payload(starts=[], known=True, working=False), "13:00", "day_unavailable"),
        (_slots_payload(starts=[]), "13:00", "slot_unavailable"),
        (_slots_payload(), "13:10", "slot_not_on_grid"),
    ],
)
def test_booking_guard_rejects_invalid_or_stale_slots(monkeypatch, slots, start_time, expected):
    _set_context(monkeypatch)
    _set_key(monkeypatch)

    def fake_call_backend(**kwargs):
        if kwargs["path"].endswith("/exact"):
            return {
                "ok": True,
                "action": "find_client",
                "result": {
                    "found": True,
                    "client": {"public_name": "Анна", "phone": None},
                },
            }
        if kwargs["path"].endswith("/slots"):
            return {"ok": True, "action": "free_slots", "result": slots}
        if kwargs["path"].endswith("/day"):
            return {
                "ok": True,
                "action": "day_view",
                "result": {"bookings": []},
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
                "start_time": start_time,
                "confirmed": True,
            }
        )
    )
    assert result["ok"] is False
    assert result["error"]["code"] == expected


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
        pytest.fail("slots and booking must not be called")

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
