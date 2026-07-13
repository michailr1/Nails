import json
from types import SimpleNamespace

import pytest
from nails_scheduling import register, schemas, tools


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


def test_schema_exposes_only_public_business_arguments():
    parameters = schemas.NAILS_SCHEDULING["parameters"]
    assert parameters["additionalProperties"] is False
    assert set(parameters["properties"]) == {
        "action",
        "day",
        "service_name",
        "client_public_name",
        "phone",
        "start_time",
        "confirmed",
    }
    assert parameters["properties"]["action"]["enum"] == [
        "list_services",
        "day_view",
        "free_slots",
        "find_client",
        "create_client",
        "create_booking",
    ]
    serialized = json.dumps(schemas.NAILS_SCHEDULING).lower()
    for forbidden in (
        "telegram_user_id",
        "chat_id",
        "request_id",
        "idempotency_key",
        "api_key",
        "internal_key",
        "headers",
        "url",
        "service_id",
        "client_id",
        "booking_id",
        "price_amount",
        "duration_minutes",
        "buffer_before_minutes",
        "buffer_after_minutes",
    ):
        assert forbidden not in serialized


def test_plugin_registers_one_dedicated_toolset():
    calls = []
    ctx = SimpleNamespace(register_tool=lambda **kwargs: calls.append(kwargs))
    register(ctx)
    assert len(calls) == 1
    assert calls[0]["name"] == "nails_scheduling"
    assert calls[0]["toolset"] == "nails_scheduling"
    assert calls[0]["handler"] is tools.nails_scheduling


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
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )
    result = json.loads(tools.nails_scheduling({"action": "list_services"}))
    assert result["error"]["code"] == "trusted_context_required"


def test_identity_spoofing_is_rejected_before_http(monkeypatch):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )
    result = json.loads(
        tools.nails_scheduling(
            {"action": "day_view", "day": "2026-07-18", "telegram_user_id": "9"}
        )
    )
    assert result["error"]["code"] == "invalid_arguments"


def test_missing_key_fails_before_http(monkeypatch):
    _set_context(monkeypatch)
    monkeypatch.delenv("NAILS_INTERNAL_API_KEY", raising=False)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )
    result = json.loads(tools.nails_scheduling({"action": "list_services"}))
    assert result["error"]["code"] == "plugin_not_configured"


@pytest.mark.parametrize(
    "args",
    [
        {"action": "list_services", "day": "2026-07-18"},
        {"action": "day_view"},
        {"action": "day_view", "day": "18.07.2026"},
        {"action": "free_slots", "day": "2026-07-18"},
        {"action": "find_client", "client_public_name": ""},
        {"action": "create_client", "client_public_name": "Анна", "confirmed": False},
        {
            "action": "create_booking",
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "day": "2026-07-18",
            "start_time": "13:00",
            "confirmed": False,
        },
        {"action": "unknown"},
    ],
)
def test_invalid_argument_combinations_are_rejected(monkeypatch, args):
    _set_context(monkeypatch)
    _set_key(monkeypatch)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: pytest.fail("backend must not be called"),
    )
    result = json.loads(tools.nails_scheduling(args))
    assert result["error"]["code"] == "invalid_arguments"
