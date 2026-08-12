from __future__ import annotations

import json
import logging
import re
from typing import Any

from .portal import build_login_url
from .tools import TrustedContextError, _api_key, _trusted_telegram_user_id
from .transport import _call_backend, _error

logger = logging.getLogger(__name__)
_ALLOWED_ACTIONS = {"read", "approve", "deny"}
_ALLOWED_STATUSES = {
    "pending",
    "approved",
    "denied",
    "expired",
    "locked",
    "consumed",
    "continued",
    "not_found",
}
_CONTINUATION_TOKEN_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[0-9a-f]{64}$"
)


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _validate(args: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(args, dict) or set(args) != {"action", "verification_number"}:
        raise ValueError("invalid arguments")
    action = args.get("action")
    number = args.get("verification_number")
    if action not in _ALLOWED_ACTIONS:
        raise ValueError("invalid action")
    if not isinstance(number, str) or len(number) != 6 or not number.isdigit():
        raise ValueError("invalid verification number")
    return action, number


def _sanitize_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("invalid backend response")
    status = result.get("status")
    remaining_seconds = result.get("remaining_seconds")
    if status not in _ALLOWED_STATUSES:
        raise ValueError("invalid status")
    if not isinstance(remaining_seconds, int) or remaining_seconds < 0:
        raise ValueError("invalid ttl")
    safe_result: dict[str, Any] = {
        "status": status,
        "remaining_seconds": remaining_seconds,
    }
    continuation_token = result.get("continuation_token")
    if continuation_token is not None:
        if status != "approved" or not isinstance(continuation_token, str):
            raise ValueError("invalid continuation token")
        if _CONTINUATION_TOKEN_RE.fullmatch(continuation_token) is None:
            raise ValueError("invalid continuation token")
        safe_result["login_url"] = build_login_url(continuation_token)
    return safe_result


def web_login(args: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        action, verification_number = _validate(args)
        telegram_user_id = _trusted_telegram_user_id()
        api_key = _api_key()
        if action == "read":
            response = _call_backend(
                action="web_login_read",
                telegram_user_id=telegram_user_id,
                api_key=api_key,
                method="GET",
                path="/api/v1/web-auth/conversation/challenge",
                params={"verification_number": verification_number},
                json_body=None,
            )
        else:
            response = _call_backend(
                action=f"web_login_{action}",
                telegram_user_id=telegram_user_id,
                api_key=api_key,
                method="POST",
                path="/api/v1/web-auth/conversation/decision",
                params=None,
                json_body={
                    "verification_number": verification_number,
                    "decision": action,
                },
            )
        if not response.get("ok"):
            return _json_response(response)
        safe_result = _sanitize_result(response.get("result"))
        return _json_response({"ok": True, "action": action, "result": safe_result})
    except ValueError:
        return _json_response(
            _error("invalid_arguments", "Web login tool received invalid arguments.")
        )
    except TrustedContextError:
        return _json_response(
            _error(
                "trusted_context_required",
                "Web login confirmation is available only from a trusted Telegram session.",
            )
        )
    except RuntimeError:
        logger.error("Web login plugin configuration is unavailable")
        return _json_response(
            _error("plugin_not_configured", "Web login integration is not configured.")
        )
    except Exception:
        logger.exception("Unexpected web login tool failure")
        return _json_response(
            _error("internal_tool_error", "Web login integration failed safely.")
        )
