from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_BASE_URL = "http://127.0.0.1:8210"
_RETRYABLE_STATUS_CODES = {502, 503, 504}
_TIMEOUT = httpx.Timeout(5.0, connect=1.0)
_ALLOWED_BACKEND_ERRORS = {
    "availability_unknown",
    "booking_outside_availability",
    "booking_overlap",
    "client_contact_conflict",
    "client_not_found",
    "idempotency_conflict",
    "service_not_found",
}


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None,
    json_body: dict[str, Any] | None,
) -> httpx.Response:
    return httpx.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_body,
        timeout=_TIMEOUT,
        follow_redirects=False,
    )


def _safe_backend_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return "backend_error"
    if not isinstance(body, dict):
        return "backend_error"
    detail = body.get("detail")
    if not isinstance(detail, dict):
        return "backend_error"
    code = detail.get("code")
    if code not in _ALLOWED_BACKEND_ERRORS:
        return "backend_error"
    return code


def _call_backend(
    *,
    action: str,
    telegram_user_id: str,
    api_key: str,
    method: str,
    path: str,
    params: dict[str, Any] | None,
    json_body: dict[str, Any] | None,
    request: Callable[..., httpx.Response] = _http_request,
) -> dict[str, Any]:
    operation_token = uuid.uuid4().hex
    request_id = f"nails-scheduling-{operation_token}"
    if action == "create_booking" and json_body is not None:
        json_body = {
            **json_body,
            "idempotency_key": f"nails-scheduling-v2-{operation_token}",
        }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Nails-Internal-Key": api_key,
        "X-Telegram-User-ID": telegram_user_id,
        "X-Request-ID": request_id,
    }
    url = f"{_API_BASE_URL}{path}"

    response: httpx.Response | None = None
    for attempt in range(2):
        try:
            response = request(
                method,
                url,
                headers=headers,
                params=params,
                json_body=json_body,
            )
        except httpx.TransportError:
            if attempt == 0:
                time.sleep(0.2)
                continue
            logger.warning(
                "Nails scheduling transport failure action=%s request_id=%s",
                action,
                request_id,
            )
            return _error(
                "service_unavailable",
                "Scheduling service is temporarily unavailable.",
            )

        if response.status_code in _RETRYABLE_STATUS_CODES and attempt == 0:
            time.sleep(0.2)
            continue
        break

    if response is None:
        return _error(
            "service_unavailable",
            "Scheduling service is temporarily unavailable.",
        )

    if response.status_code == 200:
        try:
            result = response.json()
        except ValueError:
            result = None
        if isinstance(result, dict):
            return {"ok": True, "action": action, "result": result}
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    if response.status_code in {401, 403}:
        return _error(
            "access_denied",
            "This Telegram account cannot use scheduling.",
        )

    if response.status_code in {404, 409, 422}:
        return _error(
            _safe_backend_detail(response),
            "The scheduling request could not be completed.",
        )

    logger.warning(
        "Nails scheduling backend failure status=%s action=%s request_id=%s",
        response.status_code,
        action,
        request_id,
    )
    return _error(
        "service_unavailable",
        "Scheduling service is temporarily unavailable.",
    )
