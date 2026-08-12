import json
from types import SimpleNamespace

import nails_scheduling
from nails_scheduling import presentation_guard

LOGIN_URL = (
    "https://de.funti.cc:8446/web/api/auth/continue?token="
    "123e4567-e89b-12d3-a456-426614174000."
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _approved_result(*, remaining_seconds=45):
    return json.dumps(
        {
            "ok": True,
            "action": "approve",
            "result": {
                "status": "approved",
                "remaining_seconds": remaining_seconds,
                "login_url": LOGIN_URL,
            },
        }
    )


def setup_function():
    presentation_guard._reset_for_tests()


def test_registers_deterministic_login_hooks_when_web_login_enabled(monkeypatch):
    monkeypatch.setenv("NAILS_WEB_LOGIN_TOOL_ENABLED", "true")
    tools = []
    hooks = []
    ctx = SimpleNamespace(
        register_tool=lambda **kwargs: tools.append(kwargs),
        register_hook=lambda name, callback: hooks.append((name, callback)),
    )

    nails_scheduling.register(ctx)

    assert {tool["name"] for tool in tools} == {
        "nails_scheduling",
        "save_feedback",
        "web_login",
    }
    assert hooks == [
        ("post_tool_call", presentation_guard.capture_web_login_result),
        ("transform_llm_output", presentation_guard.enforce_login_url),
    ]


def test_missing_url_is_appended_deterministically():
    presentation_guard.capture_web_login_result(
        tool_name="web_login",
        result=_approved_result(),
        session_id="session-1",
        turn_id="turn-1",
    )

    transformed = presentation_guard.enforce_login_url(
        response_text="Вход подтверждён.",
        session_id="session-1",
        platform="telegram",
    )

    assert transformed == f"Вход подтверждён.\n\nОткрыть кабинет:\n{LOGIN_URL}"
    assert "continuation_token" not in transformed


def test_existing_exact_url_is_not_duplicated_and_state_is_consumed():
    presentation_guard.capture_web_login_result(
        tool_name="web_login",
        result=_approved_result(),
        session_id="session-2",
        turn_id="turn-2",
    )
    reply = f"Вход подтверждён. Открыть кабинет: {LOGIN_URL}"

    assert (
        presentation_guard.enforce_login_url(
            response_text=reply,
            session_id="session-2",
            platform="telegram",
        )
        is None
    )
    assert (
        presentation_guard.enforce_login_url(
            response_text="Следующий ответ",
            session_id="session-2",
            platform="telegram",
        )
        is None
    )


def test_read_deny_error_and_other_tools_never_arm_guard():
    cases = [
        (
            "web_login",
            json.dumps(
                {
                    "ok": True,
                    "action": "deny",
                    "result": {"status": "denied", "remaining_seconds": 0},
                }
            ),
        ),
        (
            "web_login",
            json.dumps({"ok": False, "error": {"code": "bad"}}),
        ),
        ("nails_scheduling", _approved_result()),
    ]

    for index, (tool_name, result) in enumerate(cases):
        session_id = f"session-{index + 10}"
        presentation_guard.capture_web_login_result(
            tool_name=tool_name,
            result=result,
            session_id=session_id,
            turn_id=f"turn-{index}",
        )
        assert (
            presentation_guard.enforce_login_url(
                response_text="Вход подтверждён.",
                session_id=session_id,
                platform="telegram",
            )
            is None
        )


def test_non_telegram_output_does_not_receive_login_url():
    presentation_guard.capture_web_login_result(
        tool_name="web_login",
        result=_approved_result(),
        session_id="session-20",
        turn_id="turn-20",
    )

    assert (
        presentation_guard.enforce_login_url(
            response_text="Вход подтверждён.",
            session_id="session-20",
            platform="cli",
        )
        is None
    )


def test_expired_pending_url_is_not_emitted(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(presentation_guard, "_now", lambda: now[0])
    presentation_guard.capture_web_login_result(
        tool_name="web_login",
        result=_approved_result(remaining_seconds=1),
        session_id="session-30",
        turn_id="turn-30",
    )
    now[0] = 102.0

    assert (
        presentation_guard.enforce_login_url(
            response_text="Вход подтверждён.",
            session_id="session-30",
            platform="telegram",
        )
        is None
    )


def test_later_web_login_failure_clears_pending_url():
    presentation_guard.capture_web_login_result(
        tool_name="web_login",
        result=_approved_result(),
        session_id="session-40",
        turn_id="turn-40",
    )
    presentation_guard.capture_web_login_result(
        tool_name="web_login",
        result=json.dumps(
            {
                "ok": True,
                "action": "read",
                "result": {"status": "approved", "remaining_seconds": 30},
            }
        ),
        session_id="session-40",
        turn_id="turn-41",
    )

    assert (
        presentation_guard.enforce_login_url(
            response_text="Вход подтверждён.",
            session_id="session-40",
            platform="telegram",
        )
        is None
    )
