import json

import httpx
import pytest
from nails_scheduling import feedback_tool


def _trusted_context(monkeypatch):
    monkeypatch.setattr(feedback_tool, "_trusted_telegram_user_id", lambda: "700000001")
    monkeypatch.setattr(feedback_tool, "_api_key", lambda: "k" * 64)


def _configured_telegram(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("NAILS_BACKUP_TELEGRAM_CHAT_ID", "800000001")


def test_save_feedback_notifies_admin_with_exact_backend_context(monkeypatch):
    _trusted_context(monkeypatch)
    _configured_telegram(monkeypatch)
    captured = {}
    sent = {}

    context = [
        {
            "role": "assistant",
            "text": "Нет, завтра — 2026-07-17. 2026-07-18 будет послезавтра.",
        },
        {"role": "user", "text": "👎"},
    ]

    def fake_call_backend(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "result": {
                "saved": True,
                "feedback_id": "private",
                "safe_context": context,
            },
        }

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def fake_post(url, *, json, timeout):
        sent.update({"url": url, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setattr(feedback_tool, "_call_backend", fake_call_backend)
    monkeypatch.setattr(feedback_tool.httpx, "post", fake_post)

    result = json.loads(
        feedback_tool.save_feedback(
            {
                "kind": "thumbs_down",
                "context": context,
            }
        )
    )

    assert result == {
        "ok": True,
        "action": "save_feedback",
        "result": {"saved": True, "admin_notified": True},
    }
    assert captured["telegram_user_id"] == "700000001"
    assert captured["path"] == "/api/v1/feedback"
    assert captured["json_body"]["kind"] == "thumbs_down"
    notification = sent["json"]["text"]
    assert "2026-07-17" in notification
    assert "2026-07-18" in notification
    assert "<phone>" not in notification
    assert sent["json"]["chat_id"] == "800000001"
    assert "feedback_id" not in result["result"]
    assert "safe_context" not in result["result"]


def test_saved_feedback_survives_telegram_failure(monkeypatch):
    _trusted_context(monkeypatch)
    _configured_telegram(monkeypatch)
    monkeypatch.setattr(
        feedback_tool,
        "_call_backend",
        lambda **kwargs: {
            "ok": True,
            "result": {
                "saved": True,
                "feedback_id": "private",
                "safe_context": [{"role": "user", "text": "не то"}],
            },
        },
    )

    def failed_post(*args, **kwargs):
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(feedback_tool.httpx, "post", failed_post)
    result = json.loads(
        feedback_tool.save_feedback(
            {
                "kind": "thumbs_down",
                "context": [{"role": "user", "text": "не то"}],
            }
        )
    )

    assert result["ok"] is True
    assert result["result"] == {"saved": True, "admin_notified": False}


def test_saved_feedback_survives_missing_telegram_configuration(monkeypatch):
    _trusted_context(monkeypatch)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("NAILS_BACKUP_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(
        feedback_tool,
        "_call_backend",
        lambda **kwargs: {
            "ok": True,
            "result": {
                "saved": True,
                "feedback_id": "private",
                "safe_context": [{"role": "user", "text": "не то"}],
            },
        },
    )
    monkeypatch.setattr(
        feedback_tool.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail("Telegram must not be called"),
    )

    result = json.loads(
        feedback_tool.save_feedback(
            {
                "kind": "thumbs_down",
                "context": [{"role": "user", "text": "не то"}],
            }
        )
    )

    assert result["ok"] is True
    assert result["result"] == {"saved": True, "admin_notified": False}


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"kind": "other", "context": [{"role": "user", "text": "не то"}]},
        {"kind": "thumbs_down", "context": []},
        {
            "kind": "thumbs_down",
            "context": [{"role": "system", "text": "hidden"}],
        },
        {
            "kind": "thumbs_down",
            "context": [{"role": "user", "text": "x" * 1001}],
        },
        {
            "kind": "thumbs_down",
            "context": [{"role": "user", "text": "не то"}],
            "telegram_user_id": "9",
        },
    ],
)
def test_save_feedback_rejects_unbounded_or_spoofed_arguments(monkeypatch, args):
    monkeypatch.setattr(
        feedback_tool,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )

    result = json.loads(feedback_tool.save_feedback(args))

    assert result["error"]["code"] == "invalid_arguments"
