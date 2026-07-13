from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from datetime import time as wall_time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_BASE_URL = "http://127.0.0.1:8210"
_API_KEY_ENV = "NAILS_INTERNAL_API_KEY"
_ALLOWED_SECTIONS = {"schedule", "services", "buffers", "bookings"}
_ALLOWED_STYLES = {"business", "friendly", "casual", "playful", "custom"}
_ALLOWED_ACTIONS = {
    "start",
    "get_state",
    "get_master_preferences",
    "save_master_name",
    "save_master_style",
    "save_schedule_day",
    "save_section",
    "confirm_section",
    "pause",
    "resume",
    "complete",
}
_PAYLOAD_ACTIONS = {
    "save_master_name",
    "save_master_style",
    "save_schedule_day",
    "save_section",
}
_RETRYABLE_STATUS_CODES = {502, 503, 504}
_TIMEOUT = httpx.Timeout(5.0, connect=1.0)


class ToolInputError(ValueError):
    pass


class TrustedContextError(RuntimeError):
    pass


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _get_session_env(name: str, default: str = "") -> str:
    from gateway.session_context import get_session_env

    return get_session_env(name, default)


def _trusted_telegram_user_id() -> str:
    platform = _get_session_env("HERMES_SESSION_PLATFORM", "").strip().lower()
    user_id = _get_session_env("HERMES_SESSION_USER_ID", "").strip()

    if platform != "telegram":
        raise TrustedContextError("trusted Telegram context is required")
    if not user_id.isdigit() or int(user_id) <= 0:
        raise TrustedContextError("trusted Telegram user identity is missing")
    return user_id


def _api_key() -> str:
    value = os.getenv(_API_KEY_ENV, "").strip()
    if len(value) < 32:
        raise RuntimeError("Nails onboarding plugin is not configured")
    return value


def _normalize_text(value: Any, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ToolInputError(f"{field_name} must be a string")
    candidate = " ".join(value.split())
    if not candidate or len(candidate) > max_length:
        raise ToolInputError(f"{field_name} is invalid")
    return candidate


def _normalize_master_name(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"preferred_name"}:
        raise ToolInputError("preferred_name payload is required")
    return {
        "preferred_name": _normalize_text(value.get("preferred_name"), "preferred_name", 160)
    }


def _normalize_master_style(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolInputError("style payload is required")
    if set(value) - {"style", "details"}:
        raise ToolInputError("unsupported style fields")

    style = value.get("style")
    if style not in _ALLOWED_STYLES:
        raise ToolInputError("unsupported assistant style")

    details_value = value.get("details")
    details = None
    if details_value is not None:
        details = _normalize_text(details_value, "details", 500)
    if style == "custom" and details is None:
        raise ToolInputError("custom style requires details")

    result: dict[str, Any] = {"style": style}
    if details is not None:
        result["details"] = details
    return result


def _normalize_clock(value: Any, field_name: str) -> wall_time:
    if not isinstance(value, str):
        raise ToolInputError(f"{field_name} must be a time string")
    try:
        parsed = wall_time.fromisoformat(value)
    except ValueError as exc:
        raise ToolInputError(f"{field_name} must use HH:MM format") from exc
    if parsed.second or parsed.microsecond:
        raise ToolInputError(f"{field_name} must use minute precision")
    return parsed


def _normalize_schedule_day(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolInputError("payload object is required for save_schedule_day")

    allowed_keys = {"weekday", "is_working", "start_time", "end_time"}
    if set(value) - allowed_keys:
        raise ToolInputError("unsupported schedule day fields")

    weekday = value.get("weekday")
    if isinstance(weekday, bool) or not isinstance(weekday, int) or not 0 <= weekday <= 6:
        raise ToolInputError("weekday must be an integer from 0 to 6")

    is_working = value.get("is_working")
    if not isinstance(is_working, bool):
        raise ToolInputError("is_working must be a boolean")

    start_value = value.get("start_time")
    end_value = value.get("end_time")

    if not is_working:
        if start_value is not None or end_value is not None:
            raise ToolInputError("a non-working day must not include working hours")
        return {"weekday": weekday, "is_working": False}

    start_time = _normalize_clock(start_value, "start_time")
    end_time = _normalize_clock(end_value, "end_time")
    if end_time <= start_time:
        raise ToolInputError("end_time must be later than start_time")

    return {
        "weekday": weekday,
        "is_working": True,
        "start_time": start_time.isoformat(timespec="minutes"),
        "end_time": end_time.isoformat(timespec="minutes"),
    }


def _validate_args(
    args: dict[str, Any],
) -> tuple[str, str | None, dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(args, dict):
        raise ToolInputError("tool arguments must be an object")

    allowed_keys = {"action", "section", "payload"}
    unexpected = sorted(set(args) - allowed_keys)
    if unexpected:
        raise ToolInputError("unsupported tool arguments")

    action = args.get("action")
    if action not in _ALLOWED_ACTIONS:
        raise ToolInputError("unsupported onboarding action")

    section = args.get("section")
    payload = args.get("payload")

    if action in {"save_section", "confirm_section"} and section not in _ALLOWED_SECTIONS:
        raise ToolInputError("a valid onboarding section is required")
    if action not in {"save_section", "confirm_section"} and section is not None:
        raise ToolInputError("section is not allowed for this action")

    if action in _PAYLOAD_ACTIONS and not isinstance(payload, dict):
        raise ToolInputError("payload object is required for this action")
    if action not in _PAYLOAD_ACTIONS and payload is not None:
        raise ToolInputError("payload is not allowed for this action")

    normalized_schedule_day = None
    if action == "save_master_name":
        payload = _normalize_master_name(payload)
    elif action == "save_master_style":
        payload = _normalize_master_style(payload)
    elif action == "save_schedule_day":
        normalized_schedule_day = _normalize_schedule_day(payload)
        payload = normalized_schedule_day

    return action, section, payload, normalized_schedule_day


def _request_spec(
    action: str,
    section: str | None,
    payload: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any] | None]:
    if action == "start":
        return "POST", "/api/v1/onboarding/start", None
    if action == "get_state":
        return "GET", "/api/v1/onboarding", None
    if action == "get_master_preferences":
        return "GET", "/api/v1/onboarding/preferences", None
    if action == "save_master_name":
        return "PUT", "/api/v1/onboarding/preferences/name", payload
    if action == "save_master_style":
        return "PUT", "/api/v1/onboarding/preferences/style", payload
    if action == "save_section":
        return "PUT", f"/api/v1/onboarding/sections/{section}", {"payload": payload}
    if action == "confirm_section":
        return "POST", f"/api/v1/onboarding/sections/{section}/confirm", None
    if action == "pause":
        return "POST", "/api/v1/onboarding/pause", None
    if action == "resume":
        return "POST", "/api/v1/onboarding/resume", None
    if action == "complete":
        return "POST", "/api/v1/onboarding/complete", None
    raise ToolInputError("unsupported onboarding action")


def _http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any] | None,
) -> httpx.Response:
    return httpx.request(
        method,
        url,
        headers=headers,
        json=json_body,
        timeout=_TIMEOUT,
        follow_redirects=False,
    )


def _safe_backend_detail(response: httpx.Response) -> tuple[str, Any | None]:
    try:
        body = response.json()
    except ValueError:
        return "backend_error", None

    if not isinstance(body, dict):
        return "backend_error", None

    detail = body.get("detail")
    if not isinstance(detail, dict):
        return "backend_error", None

    code = detail.get("code")
    if not isinstance(code, str) or not code:
        return "backend_error", None

    details = detail.get("details")
    safe_detail_types = (dict, list, str, int, float, bool)
    if details is not None and not isinstance(details, safe_detail_types):
        details = None
    return code, details


def _call_backend(
    *,
    action: str,
    telegram_user_id: str,
    api_key: str,
    method: str,
    path: str,
    json_body: dict[str, Any] | None,
    request: Callable[..., httpx.Response] = _http_request,
) -> dict[str, Any]:
    request_id = f"nails-plugin-{uuid.uuid4()}"
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
                json_body=json_body,
            )
        except httpx.TransportError:
            if attempt == 0:
                time.sleep(0.2)
                continue
            logger.warning(
                "Nails onboarding transport failure action=%s request_id=%s",
                action,
                request_id,
            )
            return {
                "ok": False,
                "error": {
                    "code": "service_unavailable",
                    "message": "Onboarding service is temporarily unavailable.",
                },
            }

        if response.status_code in _RETRYABLE_STATUS_CODES and attempt == 0:
            time.sleep(0.2)
            continue
        break

    if response is None:
        return {
            "ok": False,
            "error": {
                "code": "service_unavailable",
                "message": "Onboarding service is temporarily unavailable.",
            },
        }

    if response.status_code == 200:
        try:
            result = response.json()
        except ValueError:
            result = None
        if isinstance(result, dict):
            return {"ok": True, "action": action, "result": result}
        return {
            "ok": False,
            "error": {
                "code": "invalid_backend_response",
                "message": "Onboarding service returned an invalid response.",
            },
        }

    if response.status_code in {401, 403}:
        return {
            "ok": False,
            "error": {
                "code": "access_denied",
                "message": "This Telegram account is not allowed to use onboarding.",
            },
        }

    if response.status_code in {404, 409, 422}:
        code, details = _safe_backend_detail(response)
        error: dict[str, Any] = {
            "code": code,
            "message": "The onboarding request could not be completed.",
        }
        if details is not None:
            error["details"] = details
        return {"ok": False, "error": error}

    logger.warning(
        "Nails onboarding backend failure status=%s action=%s request_id=%s",
        response.status_code,
        action,
        request_id,
    )
    return {
        "ok": False,
        "error": {
            "code": "service_unavailable",
            "message": "Onboarding service is temporarily unavailable.",
        },
    }


def _existing_schedule_days(state_result: dict[str, Any]) -> list[dict[str, Any]]:
    result = state_result.get("result")
    if not isinstance(result, dict):
        return []

    sections = result.get("sections")
    if not isinstance(sections, list):
        return []

    for section in sections:
        if not isinstance(section, dict) or section.get("section") != "schedule":
            continue
        draft_payload = section.get("draft_payload")
        if not isinstance(draft_payload, dict):
            return []
        days = draft_payload.get("days")
        if not isinstance(days, list):
            return []
        return [day for day in days if isinstance(day, dict)]
    return []


def _save_schedule_day(
    *,
    schedule_day: dict[str, Any],
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    state_result = _call_backend(
        action="get_state",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="GET",
        path="/api/v1/onboarding",
        json_body=None,
    )
    if not state_result.get("ok"):
        return state_result

    merged_days: dict[int, dict[str, Any]] = {}
    for day in _existing_schedule_days(state_result):
        weekday = day.get("weekday")
        if isinstance(weekday, int) and not isinstance(weekday, bool) and 0 <= weekday <= 6:
            merged_days[weekday] = day
    merged_days[schedule_day["weekday"]] = schedule_day

    payload = {"days": [merged_days[key] for key in sorted(merged_days)]}
    return _call_backend(
        action="save_schedule_day",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="PUT",
        path="/api/v1/onboarding/sections/schedule",
        json_body={"payload": payload},
    )


def nails_onboarding(args: dict[str, Any], **kwargs: Any) -> str:
    del kwargs

    try:
        action, section, payload, schedule_day = _validate_args(args)
        telegram_user_id = _trusted_telegram_user_id()
        api_key = _api_key()
        if action == "save_schedule_day":
            if schedule_day is None:
                raise ToolInputError("schedule day is required")
            result = _save_schedule_day(
                schedule_day=schedule_day,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
            )
        else:
            method, path, json_body = _request_spec(action, section, payload)
            result = _call_backend(
                action=action,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
                method=method,
                path=path,
                json_body=json_body,
            )
        return _json_response(result)
    except ToolInputError:
        return _json_response(
            {
                "ok": False,
                "error": {
                    "code": "invalid_arguments",
                    "message": "The onboarding tool received invalid arguments.",
                },
            }
        )
    except TrustedContextError:
        return _json_response(
            {
                "ok": False,
                "error": {
                    "code": "trusted_context_required",
                    "message": "Onboarding is available only from a trusted Telegram session.",
                },
            }
        )
    except RuntimeError:
        logger.error("Nails onboarding plugin configuration is unavailable")
        return _json_response(
            {
                "ok": False,
                "error": {
                    "code": "plugin_not_configured",
                    "message": "Onboarding integration is not configured.",
                },
            }
        )
    except Exception:
        logger.exception("Unexpected Nails onboarding plugin failure")
        return _json_response(
            {
                "ok": False,
                "error": {
                    "code": "internal_tool_error",
                    "message": "Onboarding integration failed safely.",
                },
            }
        )
