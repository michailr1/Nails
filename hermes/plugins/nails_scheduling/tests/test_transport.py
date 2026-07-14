import json
from uuid import UUID

import httpx
from nails_scheduling import transport


def _response(status_code, payload, method="GET", path="/test"):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request(method, f"http://127.0.0.1:8210{path}"),
    )


def test_unauthorized_and_forbidden_are_indistinguishable():
    common = {
        "action": "day_view",
        "telegram_user_id": "700000001",
        "api_key": "s" * 64,
        "method": "GET",
        "path": "/api/v1/scheduling/day",
        "params": {"day": "2026-07-18"},
        "json_body": None,
    }
    unauthorized = transport._call_backend(
        **common,
        request=lambda *args, **kwargs: _response(401, {"detail": {"code": "unauthorized"}}),
    )
    forbidden = transport._call_backend(
        **common,
        request=lambda *args, **kwargs: _response(403, {"detail": {"code": "forbidden"}}),
    )
    assert unauthorized == forbidden
    assert unauthorized["error"]["code"] == "access_denied"


def test_retry_reuses_request_id_and_fixed_loopback_url(monkeypatch):
    monkeypatch.setattr(transport.time, "sleep", lambda _: None)
    calls = []

    def fake_request(method, url, *, headers, params, json_body):
        calls.append({"method": method, "url": url, "headers": headers.copy(), "params": params})
        if len(calls) == 1:
            return _response(503, {"detail": {"code": "temporary"}})
        return _response(200, {"services": []})

    result = transport._call_backend(
        action="list_services",
        telegram_user_id="700000001",
        api_key="s" * 64,
        method="GET",
        path="/api/v1/scheduling/services",
        params=None,
        json_body=None,
        request=fake_request,
    )
    assert result["ok"] is True
    assert len(calls) == 2
    assert calls[0]["url"] == "http://127.0.0.1:8210/api/v1/scheduling/services"
    assert calls[0]["headers"]["X-Request-ID"] == calls[1]["headers"]["X-Request-ID"]
    assert calls[0]["headers"]["X-Telegram-User-ID"] == "700000001"


def test_create_booking_key_is_new_per_invocation_and_reused_for_retry(monkeypatch):
    monkeypatch.setattr(transport.time, "sleep", lambda _: None)
    operation_ids = iter(
        (
            UUID("00000000-0000-4000-8000-000000000001"),
            UUID("00000000-0000-4000-8000-000000000002"),
        )
    )
    monkeypatch.setattr(transport.uuid, "uuid4", lambda: next(operation_ids))

    first_calls = []

    def first_request(method, url, *, headers, params, json_body):
        first_calls.append(
            {
                "headers": headers.copy(),
                "json_body": json_body.copy(),
            }
        )
        if len(first_calls) == 1:
            return _response(503, {"detail": {"code": "temporary"}})
        return _response(200, {"booking": {"status": "scheduled"}, "created": True})

    common = {
        "action": "create_booking",
        "telegram_user_id": "700000001",
        "api_key": "s" * 64,
        "method": "POST",
        "path": "/api/v1/scheduling/bookings",
        "params": None,
        "json_body": {
            "client_public_name": "Анна Тестовая",
            "service_name": "Педикюр",
            "starts_at": "2026-07-17T11:00:00+02:00",
            "idempotency_key": "legacy-business-tuple-key",
        },
    }
    first = transport._call_backend(**common, request=first_request)

    assert first["ok"] is True
    assert len(first_calls) == 2
    first_key = first_calls[0]["json_body"]["idempotency_key"]
    assert first_key == first_calls[1]["json_body"]["idempotency_key"]
    assert first_key == "nails-scheduling-v2-00000000000040008000000000000001"
    assert first_calls[0]["headers"]["X-Request-ID"] == first_calls[1]["headers"]["X-Request-ID"]
    assert first_key != "legacy-business-tuple-key"
    assert len(first_key) <= 128

    second_calls = []

    def second_request(method, url, *, headers, params, json_body):
        second_calls.append(json_body.copy())
        return _response(200, {"booking": {"status": "scheduled"}, "created": True})

    second = transport._call_backend(**common, request=second_request)

    assert second["ok"] is True
    assert len(second_calls) == 1
    second_key = second_calls[0]["idempotency_key"]
    assert second_key == "nails-scheduling-v2-00000000000040008000000000000002"
    assert second_key != first_key


def test_transport_error_returns_safe_result_without_secret(monkeypatch):
    monkeypatch.setattr(transport.time, "sleep", lambda _: None)
    secret = "secret-value-" + "x" * 40

    def failing_request(method, url, *, headers, params, json_body):
        raise httpx.ConnectError("connection failed", request=httpx.Request(method, url))

    result = transport._call_backend(
        action="list_services",
        telegram_user_id="700000001",
        api_key=secret,
        method="GET",
        path="/api/v1/scheduling/services",
        params=None,
        json_body=None,
        request=failing_request,
    )
    serialized = json.dumps(result)
    assert result["error"]["code"] == "service_unavailable"
    assert secret not in serialized
    assert "700000001" not in serialized
