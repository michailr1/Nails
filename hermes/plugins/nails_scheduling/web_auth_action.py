from __future__ import annotations

from typing import Any

from .tools import (
    ToolInputError,
    TrustedContextError,
    _api_key,
    _json_response,
    _trusted_telegram_user_id,
    nails_scheduling,
)
from .transport import _call_backend, _error


def _confirmation_code(args: dict[str, Any]) -> str:
    if set(args) != {"action", "confirmation_code"}:
        raise ToolInputError("invalid tool arguments")
    value = args.get("confirmation_code")
    if not isinstance(value, str):
        raise ToolInputError("confirmation_code must be a string")
    code = "".join(value.split())
    if len(code) != 6 or not code.isdigit():
        raise ToolInputError("confirmation_code must contain six digits")
    return code


def nails_scheduling_with_web_auth(args: dict[str, Any], **kwargs: Any) -> str:
    if not isinstance(args, dict) or args.get("action") != "approve_web_login":
        return nails_scheduling(args, **kwargs)
    try:
        code = _confirmation_code(args)
        response = _call_backend(
            action="approve_web_login",
            telegram_user_id=_trusted_telegram_user_id(),
            api_key=_api_key(),
            method="POST",
            path="/api/v1/web-auth/challenges/approve",
            params=None,
            json_body={"confirmation_code": code},
        )
        if not response.get("ok"):
            return _json_response(response)
        result = response.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("approved"), bool):
            return _json_response(
                _error(
                    "invalid_backend_response",
                    "Web login service returned an invalid response.",
                )
            )
        return _json_response(
            {
                "ok": True,
                "action": "approve_web_login",
                "result": {"approved": result["approved"]},
            }
        )
    except ToolInputError:
        return _json_response(
            _error("invalid_arguments", "The web login confirmation code is invalid.")
        )
    except TrustedContextError:
        return _json_response(
            _error(
                "trusted_context_required",
                "Web login approval is available only from a trusted Telegram session.",
            )
        )
    except RuntimeError:
        return _json_response(
            _error("plugin_not_configured", "Web login integration is not configured.")
        )
