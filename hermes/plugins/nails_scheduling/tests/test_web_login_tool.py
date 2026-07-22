import json
from types import SimpleNamespace

import pytest
from nails_scheduling import register, web_login_tool
from nails_scheduling.web_login_schema import WEB_LOGIN


def _set_identity(monkeypatch, user_id="700000001"):
    monkeypatch.setattr(web_login_tool, "_trusted_telegram_user_id", lambda: user_id)
    monkeypatch.setattr(web_login_tool, "_api_key", lambda: "k" * 64)


def test_web_login_tool_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("NAILS_WEB_LOGIN_TOOL_ENABLED", raising=False)
    calls = []
    register(SimpleNamespace(register_tool=lambda **kwargs: calls.append(kwargs)))
    assert {call["name"] for call in calls} == {"nails_scheduling", "save_feedback"}


def test_web_login_tool_registers_only_when_enabled(monkeypatch):
    monkeypatch.setenv("NAILS_WEB_LOGIN_TOOL_ENABLED", "true")
    calls = []
    register(SimpleNamespace(register_tool=lambda **kwargs: calls.append(kwargs)))
    registered = {call["name"]: call for call in calls}
    assert set(registered) == {"nails_scheduling", "save_feedback", "web_login"}
    assert registered["web_login"]["handler"] is web_login_tool.web_login


def test_schema_treats_explicit_login_commands_as_approval():
    description = WEB_LOGIN["description"]

    assert "Нэйли, подтверждаю вход: NNNNNN" in description
    assert "подтверждаю вход NNNNNN" in description
    assert "подтверди вход NNNNNN" in description
    assert "call action=approve immediately" in description
    assert "do not ask 'Подтвердить вход?' again" in description
    assert "bare six-digit number" in description
    assert "use action=read" in description


def test_read_uses_trusted_identity_and_allowlisted_endpoint(monkeypatch):
    _set_identity(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "result": {"status": "pending", "remaining_seconds": 123},
        }

    monkeypatch.setattr(web_login_tool, "_call_backend", fake_call_backend)
    result = json.loads(
        web_login_tool.web_login(
            {"action": "read", "verification_number": "637531"}
        )
    )
    assert result == {
        "ok": True,
        "action": "read",
        "result": {"status": "pending", "remaining_seconds": 123},
    }
    assert calls == [
        {
            "action": "web_login_read",
            "telegram_user_id": "700000001",
            "api_key": "k" * 64,
            "method": "GET",
            "path": "/api/v1/web-auth/conversation/challenge",
            "params": {"verification_number": "637531"},
            "json_body": None,
        }
    ]


@pytest.mark.parametrize("action", ["approve", "deny"])
def test_decision_uses_separate_mutation_action(monkeypatch, action):
    _set_identity(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        status = "approved" if action == "approve" else "denied"
        return {
            "ok": True,
            "result": {"status": status, "remaining_seconds": 45},
        }

    monkeypatch.setattr(web_login_tool, "_call_backend", fake_call_backend)
    result = json.loads(
        web_login_tool.web_login(
            {"action": action, "verification_number": "637531"}
        )
    )
    assert result["ok"] is True
    assert result["action"] == action
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/api/v1/web-auth/conversation/decision"
    assert calls[0]["json_body"] == {
        "verification_number": "637531",
        "decision": action,
    }


@pytest.mark.parametrize(
    "args",
    [
        {"action": "approve", "verification_number": "12345"},
        {"action": "approve", "verification_number": "12345x"},
        {"action": "unknown", "verification_number": "123456"},
        {
            "action": "read",
            "verification_number": "123456",
            "telegram_user_id": "9",
        },
    ],
)
def test_invalid_arguments_fail_before_transport(monkeypatch, args):
    _set_identity(monkeypatch)
    monkeypatch.setattr(
        web_login_tool,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )
    result = json.loads(web_login_tool.web_login(args))
    assert result["error"]["code"] == "invalid_arguments"


def test_trusted_context_failure_is_safe(monkeypatch):
    monkeypatch.setattr(
        web_login_tool,
        "_trusted_telegram_user_id",
        lambda: (_ for _ in ()).throw(web_login_tool.TrustedContextError()),
    )
    monkeypatch.setattr(
        web_login_tool,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )
    result = json.loads(
        web_login_tool.web_login(
            {"action": "read", "verification_number": "123456"}
        )
    )
    assert result["error"]["code"] == "trusted_context_required"
