import json

import pytest
from nails_scheduling import tools, transport


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
        "is_active": True,
        "kind": "base",
        "price_type": "fixed",
        "price_min_amount": None,
        "price_max_amount": None,
        "price_unit": None,
        "category": None,
        "sort_order": 0,
        "extra_minutes": 0,
    }


def _client_payload():
    return {
        "id": "33333333-3333-4333-8333-333333333333",
        "public_name": "Анна",
        "phone": None,
        "private_alias": None,
        "contact_channel": None,
        "birthday": None,
        "notes": None,
        "nail_skin_notes": None,
        "sensitivity_notes": None,
        "style_preferences": None,
        "communication_preferences": None,
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


@pytest.mark.parametrize(
    ("args", "method", "path", "params"),
    [
        (
            {"action": "list_services"},
            "GET",
            "/api/v1/scheduling/services",
            {"include_inactive": "false"},
        ),
        (
            {"action": "day_view", "day": "2026-07-18"},
            "GET",
            "/api/v1/scheduling/day",
            {"day": "2026-07-18"},
        ),
        (
            {"action": "free_slots", "day": "2026-07-18", "service_name": "Маникюр"},
            "GET",
            "/api/v1/scheduling/slots",
            {"day": "2026-07-18", "service_name": "Маникюр"},
        ),
        (
            {"action": "find_client", "client_public_name": "Анна"},
            "GET",
            "/api/v1/scheduling/clients/exact",
            {"public_name": "Анна"},
        ),
    ],
)
def test_read_actions_use_only_fixed_endpoints(monkeypatch, args, method, path, params):
    _set_context(monkeypatch, user_id="700000777")
    _set_key(monkeypatch)
    captured = {}

    def fake_call_backend(**kwargs):
        captured.update(kwargs)
        action = args["action"]
        if action == "list_services":
            result = {"services": []}
        elif action == "day_view":
            result = {
                "day": "2026-07-18",
                "timezone": "Europe/Berlin",
                "weekday_iso": 6,
                "availability_known": True,
                "availability": [],
                "bookings": [],
            }
        elif action == "free_slots":
            result = _slots_payload(starts=[])
        else:
            result = {"found": False, "client": None}
        return {"ok": True, "action": action, "result": result}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)
    result = json.loads(tools.nails_scheduling(args))
    assert result["ok"] is True
    assert captured["telegram_user_id"] == "700000777"
    assert captured["method"] == method
    assert captured["path"] == path
    assert captured["params"] == params
    assert captured["json_body"] is None


def test_results_strip_backend_technical_ids(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: {
            "ok": True,
            "action": "list_services",
            "result": {"services": [_service_payload()]},
        },
    )
    result = json.loads(tools.nails_scheduling({"action": "list_services"}))
    serialized = json.dumps(result)
    assert result["ok"] is True
    assert "11111111-1111-4111-8111-111111111111" not in serialized
    assert "id" not in result["result"]["services"][0]


def test_create_client_performs_exact_lookup_before_post(monkeypatch):
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
        return {
            "ok": True,
            "action": "create_client",
            "result": {
                "client": _client_payload(),
                "created": True,
                "contact_added": False,
            },
        }

    monkeypatch.setattr(transport, "_call_backend", fake_call_backend)
    result = json.loads(
        tools.nails_scheduling(
            {"action": "create_client", "client_public_name": " Анна ", "confirmed": True}
        )
    )
    assert result["ok"] is True
    assert result["result"]["created"] is True
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/clients/exact",
        "/api/v1/scheduling/clients",
    ]
    assert calls[1]["json_body"] == {
        "public_name": "Анна",
        "phone": None,
        "private_alias": None,
        "contact_channel": None,
        "birthday": None,
        "notes": None,
        "nail_skin_notes": None,
        "sensitivity_notes": None,
        "style_preferences": None,
        "communication_preferences": None,
    }
    assert "id" not in result["result"]["client"]


def test_create_client_returns_existing_without_post(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "action": "find_client",
            "result": {
                "found": True,
                "client": _client_payload(),
            },
        }

    monkeypatch.setattr(transport, "_call_backend", fake_call_backend)
    result = json.loads(
        tools.nails_scheduling(
            {"action": "create_client", "client_public_name": "Анна", "confirmed": True}
        )
    )
    assert result["ok"] is True
    assert result["result"]["created"] is False
    assert len(calls) == 1
    assert calls[0]["path"] == "/api/v1/scheduling/clients/exact"
