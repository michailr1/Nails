import importlib
import json

from nails_scheduling.web_login_schema import WEB_LOGIN

web_login_tool = importlib.import_module("nails_scheduling.web_login_tool")

TOKEN = (
    "123e4567-e89b-12d3-a456-426614174000."
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _set_identity(monkeypatch):
    monkeypatch.setattr(web_login_tool, "_trusted_telegram_user_id", lambda: "700000001")
    monkeypatch.setattr(web_login_tool, "_api_key", lambda: "k" * 64)


def test_successful_approve_returns_clickable_login_url_without_raw_token_field(monkeypatch):
    _set_identity(monkeypatch)
    monkeypatch.setattr(
        web_login_tool,
        "_call_backend",
        lambda **kwargs: {
            "ok": True,
            "result": {
                "status": "approved",
                "remaining_seconds": 45,
                "continuation_token": TOKEN,
            },
        },
    )

    result = json.loads(
        web_login_tool.web_login(
            {"action": "approve", "verification_number": "637531"}
        )
    )
    safe = result["result"]
    assert safe["status"] == "approved"
    assert safe["login_url"] == (
        "https://de.funti.cc:8446/web/api/auth/continue?token=" + TOKEN
    )
    assert "continuation_token" not in safe


def test_non_approve_result_does_not_gain_login_url(monkeypatch):
    _set_identity(monkeypatch)
    monkeypatch.setattr(
        web_login_tool,
        "_call_backend",
        lambda **kwargs: {
            "ok": True,
            "result": {"status": "denied", "remaining_seconds": 0},
        },
    )

    result = json.loads(
        web_login_tool.web_login(
            {"action": "deny", "verification_number": "637531"}
        )
    )
    assert result["result"] == {"status": "denied", "remaining_seconds": 0}


def test_schema_requires_exact_login_url_in_final_telegram_reply():
    description = WEB_LOGIN["description"]
    assert "successful approve result contains login_url" in description
    assert "MUST include that exact URL" in description
    assert "Вход подтверждён. Открыть кабинет: <login_url>" in description
    assert "Never invent or alter login_url" in description
