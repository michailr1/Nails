import json
from types import SimpleNamespace

import httpx
import pytest
from nails_onboarding import register, schemas, tools


def _set_context(monkeypatch, *, platform="telegram", user_id="100000001"):
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


def _response(status_code, payload):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("POST", "http://127.0.0.1:8210/test"),
    )


def test_schema_exposes_no_identity_url_headers_or_secret():
    parameters = schemas.NAILS_ONBOARDING["parameters"]
    assert parameters["additionalProperties"] is False
    assert set(parameters["properties"]) == {"action", "section", "payload"}
    assert "save_schedule_day" not in parameters["properties"]["action"]["enum"]
    assert parameters["properties"]["section"]["enum"] == [
        "services",
        "buffers",
        "availability",
        "bookings",
    ]
    serialized = json.dumps(schemas.NAILS_ONBOARDING).lower()
    for forbidden in (
        "telegram_user_id",
        "chat_id",
        "request_id",
        "api_key",
        "internal_key",
        "headers",
        "url",
        "weekday",
        "weekly schedule",
    ):
        assert forbidden not in serialized


def test_plugin_registers_one_dedicated_toolset():
    calls = []
    ctx = SimpleNamespace(register_tool=lambda **kwargs: calls.append(kwargs))

    register(ctx)

    assert len(calls) == 1
    assert calls[0]["name"] == "nails_onboarding"
    assert calls[0]["toolset"] == "nails_onboarding"
    assert calls[0]["handler"] is tools.nails_onboarding


def test_handler_uses_trusted_context_identity(monkeypatch):
    _set_context(monkeypatch, user_id="700000001")
    _set_key(monkeypatch)
    captured = {}

    def fake_call_backend(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "result": {"status": "in_progress"}}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(tools.nails_onboarding({"action": "start"}))

    assert result["ok"] is True
    assert captured["telegram_user_id"] == "700000001"
    assert captured["path"] == "/api/v1/onboarding/start"
    assert captured["method"] == "POST"


@pytest.mark.parametrize(
    ("platform", "user_id"),
    [
        ("cli", "700000001"),
        ("discord", "700000001"),
        ("telegram", ""),
        ("telegram", "not-a-number"),
        ("telegram", "0"),
    ],
)
def test_handler_fails_closed_without_trusted_telegram_identity(
    monkeypatch,
    platform,
    user_id,
):
    _set_context(monkeypatch, platform=platform, user_id=user_id)
    _set_key(monkeypatch)
    called = False

    def fake_call_backend(**kwargs):
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(tools.nails_onboarding({"action": "get_state"}))

    assert result["ok"] is False
    assert result["error"]["code"] == "trusted_context_required"
    assert called is False


def test_identity_spoofing_argument_is_rejected_before_http(monkeypatch):
    _set_context(monkeypatch, user_id="700000001")
    _set_key(monkeypatch)
    called = False

    def fake_call_backend(**kwargs):
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(
        tools.nails_onboarding(
            {
                "action": "start",
                "telegram_user_id": "999999999",
            }
        )
    )

    assert result["error"]["code"] == "invalid_arguments"
    assert called is False


def test_missing_plugin_key_fails_without_http(monkeypatch):
    _set_context(monkeypatch)
    monkeypatch.delenv("NAILS_INTERNAL_API_KEY", raising=False)
    called = False

    def fake_call_backend(**kwargs):
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    result = json.loads(tools.nails_onboarding({"action": "start"}))

    assert result["error"]["code"] == "plugin_not_configured"
    assert called is False


def test_save_availability_section_uses_fixed_endpoint_and_body(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    captured = {}

    def fake_call_backend(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "result": {}}

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)
    payload = {
        "days": [
            {
                "day": "2026-07-15",
                "is_available": True,
                "intervals": [
                    {"start_time": "10:00", "end_time": "14:00"},
                    {"start_time": "16:00", "end_time": "20:00"},
                ],
            }
        ]
    }

    result = json.loads(
        tools.nails_onboarding(
            {
                "action": "save_section",
                "section": "availability",
                "payload": payload,
            }
        )
    )

    assert result["ok"] is True
    assert captured["method"] == "PUT"
    assert captured["path"] == "/api/v1/onboarding/sections/availability"
    assert captured["json_body"] == {"payload": payload}


@pytest.mark.parametrize(
    "args",
    [
        {"action": "start", "section": "availability"},
        {"action": "pause", "payload": {}},
        {"action": "save_section", "section": "availability"},
        {"action": "save_section", "section": "schedule", "payload": {}},
        {"action": "save_schedule_day", "payload": {}},
        {"action": "confirm_section"},
        {"action": "unknown"},
    ],
)
def test_invalid_action_combinations_are_rejected(monkeypatch, args):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )

    result = json.loads(tools.nails_onboarding(args))

    assert result["error"]["code"] == "invalid_arguments"


def test_unauthorized_and_forbidden_are_indistinguishable():
    common = {
        "action": "get_state",
        "telegram_user_id": "700000001",
        "api_key": "s" * 64,
        "method": "GET",
        "path": "/api/v1/onboarding",
        "json_body": None,
    }

    unauthorized = tools._call_backend(
        **common,
        request=lambda *args, **kwargs: _response(401, {"detail": {"code": "unauthorized"}}),
    )
    forbidden = tools._call_backend(
        **common,
        request=lambda *args, **kwargs: _response(403, {"detail": {"code": "forbidden"}}),
    )

    assert unauthorized == forbidden
    assert unauthorized["error"]["code"] == "access_denied"
    assert "forbidden" not in json.dumps(unauthorized).lower()
    assert "unauthorized" not in json.dumps(unauthorized).lower()


def test_retry_reuses_runtime_request_id_and_fixed_loopback_url(monkeypatch):
    monkeypatch.setattr(tools.time, "sleep", lambda _: None)
    calls = []

    def fake_request(method, url, *, headers, json_body):
        calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers.copy(),
                "json_body": json_body,
            }
        )
        if len(calls) == 1:
            return _response(503, {"detail": {"code": "temporary"}})
        return _response(200, {"status": "paused"})

    result = tools._call_backend(
        action="get_state",
        telegram_user_id="700000001",
        api_key="s" * 64,
        method="GET",
        path="/api/v1/onboarding",
        json_body=None,
        request=fake_request,
    )

    assert result["ok"] is True
    assert len(calls) == 2
    assert calls[0]["url"] == "http://127.0.0.1:8210/api/v1/onboarding"
    assert calls[0]["headers"]["X-Request-ID"] == calls[1]["headers"]["X-Request-ID"]
    assert calls[0]["headers"]["X-Telegram-User-ID"] == "700000001"


def test_transport_error_returns_safe_result_without_secret(monkeypatch):
    monkeypatch.setattr(tools.time, "sleep", lambda _: None)
    secret = "secret-value-" + "x" * 40

    def failing_request(method, url, *, headers, json_body):
        raise httpx.ConnectError("connection failed", request=httpx.Request(method, url))

    result = tools._call_backend(
        action="start",
        telegram_user_id="700000001",
        api_key=secret,
        method="POST",
        path="/api/v1/onboarding/start",
        json_body=None,
        request=failing_request,
    )

    serialized = json.dumps(result)
    assert result["error"]["code"] == "service_unavailable"
    assert secret not in serialized
    assert "700000001" not in serialized


def test_safe_backend_validation_details_are_preserved():
    result = tools._call_backend(
        action="save_section",
        telegram_user_id="700000001",
        api_key="s" * 64,
        method="PUT",
        path="/api/v1/onboarding/sections/availability",
        json_body={"payload": {}},
        request=lambda *args, **kwargs: _response(
            422,
            {
                "detail": {
                    "code": "invalid_onboarding_payload",
                    "details": [
                        {
                            "type": "missing",
                            "location": ["days"],
                            "message": "Field required",
                        }
                    ],
                }
            },
        ),
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_onboarding_payload"
    assert result["error"]["details"][0]["location"] == ["days"]
