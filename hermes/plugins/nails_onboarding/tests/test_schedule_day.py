import json

import pytest
from nails_onboarding import schemas, tools


def _set_context(monkeypatch, *, user_id="700000001"):
    values = {
        "HERMES_SESSION_PLATFORM": "telegram",
        "HERMES_SESSION_USER_ID": user_id,
    }
    monkeypatch.setattr(
        tools,
        "_get_session_env",
        lambda name, default="": values.get(name, default),
    )


def _set_key(monkeypatch):
    monkeypatch.setenv("NAILS_INTERNAL_API_KEY", "k" * 64)


def test_schema_describes_incremental_schedule_action():
    action = schemas.NAILS_ONBOARDING["parameters"]["properties"]["action"]
    payload = schemas.NAILS_ONBOARDING["parameters"]["properties"]["payload"]

    assert "save_schedule_day" in action["enum"]
    assert "Monday=0" in payload["description"]
    assert "HH:MM" in payload["description"]


def test_save_schedule_day_merges_with_existing_draft(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "ok": True,
                "action": "get_state",
                "result": {
                    "sections": [
                        {
                            "section": "schedule",
                            "draft_payload": {
                                "days": [
                                    {
                                        "weekday": 1,
                                        "is_working": True,
                                        "start_time": "10:00",
                                        "end_time": "19:00",
                                    }
                                ]
                            },
                        }
                    ]
                },
            }
        return {"ok": True, "action": "save_schedule_day", "result": {}}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_onboarding(
            {
                "action": "save_schedule_day",
                "payload": {"weekday": 0, "is_working": False},
            }
        )
    )

    assert result["ok"] is True
    assert calls[0]["method"] == "GET"
    assert calls[0]["path"] == "/api/v1/onboarding"
    assert calls[1]["method"] == "PUT"
    assert calls[1]["path"] == "/api/v1/onboarding/sections/schedule"
    assert calls[1]["json_body"] == {
        "payload": {
            "days": [
                {"weekday": 0, "is_working": False},
                {
                    "weekday": 1,
                    "is_working": True,
                    "start_time": "10:00",
                    "end_time": "19:00",
                },
            ]
        }
    }


def test_save_working_day_normalizes_and_replaces_same_weekday(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "ok": True,
                "action": "get_state",
                "result": {
                    "sections": [
                        {
                            "section": "schedule",
                            "draft_payload": {
                                "days": [{"weekday": 2, "is_working": False}]
                            },
                        }
                    ]
                },
            }
        return {"ok": True, "action": "save_schedule_day", "result": {}}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_onboarding(
            {
                "action": "save_schedule_day",
                "payload": {
                    "weekday": 2,
                    "is_working": True,
                    "start_time": "09:30",
                    "end_time": "18:15",
                },
            }
        )
    )

    assert result["ok"] is True
    assert calls[1]["json_body"] == {
        "payload": {
            "days": [
                {
                    "weekday": 2,
                    "is_working": True,
                    "start_time": "09:30",
                    "end_time": "18:15",
                }
            ]
        }
    }


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"weekday": True, "is_working": False},
        {"weekday": 7, "is_working": False},
        {"weekday": 0, "is_working": "no"},
        {"weekday": 0, "is_working": False, "start_time": "10:00"},
        {"weekday": 1, "is_working": True},
        {
            "weekday": 1,
            "is_working": True,
            "start_time": "19:00",
            "end_time": "10:00",
        },
        {"weekday": 1, "is_working": False, "unknown": "value"},
    ],
)
def test_invalid_schedule_day_is_rejected_before_backend(monkeypatch, payload):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )

    args = {"action": "save_schedule_day"}
    if payload is not None:
        args["payload"] = payload

    result = json.loads(tools.nails_onboarding(args))

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_schedule_day_does_not_accept_section(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )

    result = json.loads(
        tools.nails_onboarding(
            {
                "action": "save_schedule_day",
                "section": "schedule",
                "payload": {"weekday": 0, "is_working": False},
            }
        )
    )

    assert result["error"]["code"] == "invalid_arguments"
