from __future__ import annotations

import json
import logging
import os
from typing import Any

from .operations import _create_booking, _create_client
from .presenters import _sanitize_success
from .transport import _call_backend, _error
from .validation import ToolInputError, _request_spec, _validate_args

logger = logging.getLogger(__name__)

_API_KEY_ENV = "NAILS_INTERNAL_API_KEY"


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
        raise RuntimeError("Nails scheduling plugin is not configured")
    return value


def nails_scheduling(args: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        action, values = _validate_args(args)
        telegram_user_id = _trusted_telegram_user_id()
        api_key = _api_key()
        if action == "create_client":
            response = _create_client(
                values,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
            )
        elif action == "create_booking":
            response = _create_booking(
                values,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
            )
        else:
            method, path, params, json_body = _request_spec(action, values)
            response = _call_backend(
                action=action,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
                method=method,
                path=path,
                params=params,
                json_body=json_body,
            )
        if not response.get("ok"):
            return _json_response(response)
        try:
            safe_result = _sanitize_success(action, response.get("result"))
        except (KeyError, TypeError, ValueError):
            return _json_response(
                _error(
                    "invalid_backend_response",
                    "Scheduling service returned an invalid response.",
                )
            )
        return _json_response({"ok": True, "action": action, "result": safe_result})
    except ToolInputError:
        return _json_response(
            _error(
                "invalid_arguments",
                "The scheduling tool received invalid arguments.",
            )
        )
    except TrustedContextError:
        return _json_response(
            _error(
                "trusted_context_required",
                "Scheduling is available only from a trusted Telegram session.",
            )
        )
    except RuntimeError:
        logger.error("Nails scheduling plugin configuration is unavailable")
        return _json_response(
            _error(
                "plugin_not_configured",
                "Scheduling integration is not configured.",
            )
        )
    except Exception:
        logger.exception("Unexpected Nails scheduling plugin failure")
        return _json_response(
            _error(
                "internal_tool_error",
                "Scheduling integration failed safely.",
            )
        )
