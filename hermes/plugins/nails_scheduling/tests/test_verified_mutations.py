import json

from nails_scheduling import operations, tools, verified_operations


def _set_context(monkeypatch):
    values = {
        "HERMES_SESSION_PLATFORM": "telegram",
        "HERMES_SESSION_USER_ID": "700000001",
    }
    monkeypatch.setattr(
        tools,
        "_get_session_env",
        lambda name, default="": values.get(name, default),
    )
    monkeypatch.setenv("NAILS_INTERNAL_API_KEY", "k" * 64)


def _booking(*, starts_at, status="scheduled"):
    return {
        "id": "22222222-2222-4222-8222-222222222222",
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "addon_names": [],
        "catalog_items": [
            {
                "service_id": "11111111-1111-4111-8111-111111111111",
                "kind": "base",
                "public_name": "Маникюр",
                "price_type": "fixed",
                "price_amount": "2500.00",
                "price_min_amount": None,
                "price_max_amount": None,
                "price_unit": None,
                "currency": "RUB",
                "duration_minutes": 120,
                "extra_minutes": 0,
            }
        ],
        "starts_at": starts_at,
        "ends_at": starts_at,
        "reserved_starts_at": starts_at,
        "reserved_ends_at": starts_at,
        "status": status,
        "price_amount": "2500.00",
        "currency": "RUB",
        "price_type": "fixed",
        "price_min_amount": "2500.00",
        "price_max_amount": "2500.00",
        "price_unit": None,
        "price_source": "catalog_fixed",
        "price_confirmed": True,
        "duration_minutes": 120,
        "duration_source": "catalog_v2",
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 21,
    }


def _day(day, bookings):
    return {
        "ok": True,
        "action": "day_view",
        "result": {
            "day": day,
            "timezone": "Europe/Berlin",
            "weekday_iso": 6,
            "availability_known": True,
            "availability": [],
            "bookings": bookings,
        },
    }


def test_cancel_is_prechecked_written_and_verified_in_one_tool_call(monkeypatch):
    _set_context(monkeypatch)
    calls = []
    original = _booking(starts_at="2026-07-18T13:00:00+02:00")
    cancelled = _booking(
        starts_at="2026-07-18T13:00:00+02:00",
        status="cancelled",
    )

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _day("2026-07-18", [original])
        if len(calls) == 2:
            return {
                "ok": True,
                "action": "cancel_booking",
                "result": {"booking": cancelled, "changed": True},
            }
        return _day("2026-07-18", [])

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    monkeypatch.setattr(verified_operations, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "cancel_booking",
                "client_public_name": "Анна",
                "service_name": "Маникюр",
                "day": "2026-07-18",
                "start_time": "13:00",
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["result"]["changed"] is True
    assert result["result"]["verified"] is True
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/day",
        "/api/v1/scheduling/bookings/cancel",
        "/api/v1/scheduling/day",
    ]
    assert "id" not in result["result"]["booking"]


def test_reschedule_verifies_source_and_target_days_in_one_tool_call(monkeypatch):
    _set_context(monkeypatch)
    calls = []
    original = _booking(starts_at="2026-07-18T13:00:00+02:00")
    moved = _booking(starts_at="2026-07-19T15:00:00+02:00")

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _day("2026-07-18", [original])
        if len(calls) == 2:
            return {
                "ok": True,
                "action": "reschedule_booking",
                "result": {"booking": moved, "changed": True},
            }
        if kwargs["params"]["day"] == "2026-07-18":
            return _day("2026-07-18", [])
        return _day("2026-07-19", [moved])

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    monkeypatch.setattr(verified_operations, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "reschedule_booking",
                "client_public_name": "Анна",
                "service_name": "Маникюр",
                "day": "2026-07-18",
                "start_time": "13:00",
                "new_day": "2026-07-19",
                "new_start_time": "15:00",
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["result"]["changed"] is True
    assert result["result"]["verified"] is True
    assert result["result"]["booking"]["starts_at"] == "2026-07-19T15:00:00+02:00"
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/day",
        "/api/v1/scheduling/bookings/reschedule",
        "/api/v1/scheduling/day",
        "/api/v1/scheduling/day",
    ]
    assert [call["params"] for call in calls[2:]] == [
        {"day": "2026-07-18"},
        {"day": "2026-07-19"},
    ]


def test_mutation_verification_failure_is_not_reported_as_success(monkeypatch):
    _set_context(monkeypatch)
    calls = []
    original = _booking(starts_at="2026-07-18T13:00:00+02:00")

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _day("2026-07-18", [original])
        if len(calls) == 2:
            return {
                "ok": True,
                "action": "cancel_booking",
                "result": {
                    "booking": _booking(
                        starts_at="2026-07-18T13:00:00+02:00",
                        status="cancelled",
                    ),
                    "changed": True,
                },
            }
        return _day("2026-07-18", [original])

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    monkeypatch.setattr(verified_operations, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "cancel_booking",
                "client_public_name": "Анна",
                "service_name": "Маникюр",
                "day": "2026-07-18",
                "start_time": "13:00",
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "mutation_verification_failed"
