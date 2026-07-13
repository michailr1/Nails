import json

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
