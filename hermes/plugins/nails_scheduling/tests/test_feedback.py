import json

from nails_scheduling import feedback


def test_save_feedback_uses_trusted_identity_and_bounded_context(monkeypatch):
    captured = {}

    monkeypatch.setattr(feedback, "_trusted_telegram_user_id", lambda: "700000001")
    monkeypatch.setattr(feedback, "_api_key", lambda: "k" * 64)

    def fake_call_backend(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "action": "save_feedback",
            "result": {"saved": True, "event_id": "not-public"},
        }

    monkeypatch.setattr(feedback, "_call_backend", fake_call_backend)
    result = json.loads(
        feedback.save_feedback(
            {
                "kind": "thumbs_down",
                "context": [
                    {"role": "user", "content": "не то"},
                    {"role": "assistant", "content": "Предыдущий ответ"},
                ],
            }
        )
    )

    assert result == {
        "ok": True,
        "action": "save_feedback",
        "result": {"saved": True},
    }
    assert captured["telegram_user_id"] == "700000001"
    assert captured["path"] == "/api/v1/feedback"
    assert captured["json_body"]["kind"] == "thumbs_down"
    assert "event_id" not in result["result"]


def test_save_feedback_rejects_unbounded_or_extra_input():
    result = json.loads(
        feedback.save_feedback(
            {
                "kind": "thumbs_down",
                "context": [{"role": "user", "content": "не то"}],
                "telegram_user_id": "700000001",
            }
        )
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_save_feedback_rejects_more_than_four_messages():
    result = json.loads(
        feedback.save_feedback(
            {
                "kind": "unrecognized",
                "context": [
                    {"role": "user", "content": str(index)} for index in range(5)
                ],
            }
        )
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"
