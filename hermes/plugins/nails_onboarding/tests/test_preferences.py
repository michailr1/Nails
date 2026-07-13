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


def test_schema_exposes_acquaintance_actions():
    actions = schemas.NAILS_ONBOARDING["parameters"]["properties"]["action"]["enum"]

    assert "get_master_preferences" in actions
    assert "save_master_name" in actions
    assert "save_master_style" in actions


def test_get_master_preferences_uses_fixed_endpoint(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    captured = {}

    def fake_call_backend(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "result": {"is_complete": False}}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(tools.nails_onboarding({"action": "get_master_preferences"}))

    assert result["ok"] is True
    assert captured["method"] == "GET"
    assert captured["path"] == "/api/v1/onboarding/preferences"
    assert captured["json_body"] is None


def test_save_master_name_normalizes_and_uses_fixed_endpoint(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    captured = {}

    def fake_call_backend(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "result": {"preferred_name": "Настя"}}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_onboarding(
            {
                "action": "save_master_name",
                "payload": {"preferred_name": "  Настя   "},
            }
        )
    )

    assert result["ok"] is True
    assert captured["method"] == "PUT"
    assert captured["path"] == "/api/v1/onboarding/preferences/name"
    assert captured["json_body"] == {"preferred_name": "Настя"}


def test_save_master_style_normalizes_details(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    captured = {}

    def fake_call_backend(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "result": {"assistant_style": "friendly"}}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_onboarding(
            {
                "action": "save_master_style",
                "payload": {
                    "style": "friendly",
                    "details": " тепло, но без лишних эмодзи ",
                },
            }
        )
    )

    assert result["ok"] is True
    assert captured["method"] == "PUT"
    assert captured["path"] == "/api/v1/onboarding/preferences/style"
    assert captured["json_body"] == {
        "style": "friendly",
        "details": "тепло, но без лишних эмодзи",
    }


@pytest.mark.parametrize(
    "args",
    [
        {"action": "save_master_name", "payload": {}},
        {
            "action": "save_master_name",
            "payload": {"preferred_name": "Настя", "unknown": True},
        },
        {"action": "save_master_style", "payload": {"style": "unknown"}},
        {"action": "save_master_style", "payload": {"style": "custom"}},
        {
            "action": "save_master_style",
            "section": "schedule",
            "payload": {"style": "friendly"},
        },
    ],
)
def test_invalid_preference_arguments_are_rejected_before_backend(monkeypatch, args):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )

    result = json.loads(tools.nails_onboarding(args))

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"
