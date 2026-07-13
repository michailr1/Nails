import json

from nails_scheduling import tools


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


def test_resolve_date_uses_fixed_backend_operation(monkeypatch):
    _set_context(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "action": "resolve_date",
            "result": {
                "timezone": "Europe/Berlin",
                "today": "2026-07-13",
                "today_weekday_iso": 1,
                "day": "2026-07-17",
                "weekday_iso": 5,
                "is_past": False,
                "kind": "weekday",
                "occurrence": "nearest_future",
            },
        }

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)
    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "resolve_date",
                "date_kind": "weekday",
                "weekday_iso": 5,
                "occurrence": "nearest_future",
            }
        )
    )

    assert result["ok"] is True
    assert result["result"]["day"] == "2026-07-17"
    assert result["result"]["weekday_iso"] == 5
    assert calls == [
        {
            "action": "resolve_date",
            "telegram_user_id": "700000001",
            "api_key": "k" * 64,
            "method": "POST",
            "path": "/api/v1/scheduling/date/resolve",
            "params": None,
            "json_body": {
                "kind": "weekday",
                "weekday_iso": 5,
                "occurrence": "nearest_future",
            },
        }
    ]


def test_update_availability_replaces_only_confirmed_dates(monkeypatch):
    _set_context(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "action": "update_availability",
            "result": {
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
            },
        }

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)
    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "update_availability",
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
                ],
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert [item["day"] for item in result["result"]["days"]] == [
        "2026-07-17",
        "2026-07-18",
    ]
    assert calls[0]["method"] == "PUT"
    assert calls[0]["path"] == "/api/v1/scheduling/availability"
    assert calls[0]["params"] is None
    assert calls[0]["json_body"] == {
        "days": [
            {
                "day": "2026-07-17",
                "state": "available",
                "intervals": [{"start_time": "11:00", "end_time": "15:00"}],
                "note": None,
            },
            {
                "day": "2026-07-18",
                "state": "unknown",
                "intervals": [],
                "note": None,
            },
        ]
    }
    serialized = json.dumps(result)
    assert "700000001" not in serialized
    assert "idempotency" not in serialized.lower()
