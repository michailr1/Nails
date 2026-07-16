from __future__ import annotations

import json
import logging
from typing import Any

from .tools import TrustedContextError, _api_key, _trusted_telegram_user_id
from .transport import _call_backend, _error

logger = logging.getLogger(__name__)
_ALLOWED_KINDS = {"thumbs_down", "unrecognized"}
_ALLOWED_ROLES = {"user", "assistant"}
_MAX_MESSAGES = 4
_MAX_CONTENT_LENGTH = 1000


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _validate_args(args: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(args, dict) or set(args) != {"kind", "context"}:
        raise ValueError("invalid arguments")
    kind = args.get("kind")
    context = args.get("context")
    if kind not in _ALLOWED_KINDS or not isinstance(context, list):
        raise ValueError("invalid arguments")
    if not 1 <= len(context) <= _MAX_MESSAGES:
        raise ValueError("invalid arguments")

    normalized: list[dict[str, str]] = []
    for item in context:
        if not isinstance(item, dict) or set(item) != {"role", "content"}:
            raise ValueError("invalid arguments")
        role = item.get("role")
        content = item.get("content")
        if role not in _ALLOWED_ROLES or not isinstance(content, str):
            raise ValueError("invalid arguments")
        compact = " ".join(content.split())
        if not compact or len(compact) > _MAX_CONTENT_LENGTH:
            raise ValueError("invalid arguments")
        normalized.append({"role": role, "content": compact})
    return kind, normalized


def save_feedback(args: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        kind, context = _validate_args(args)
        response = _call_backend(
            action="save_feedback",
            telegram_user_id=_trusted_telegram_user_id(),
            api_key=_api_key(),
            method="POST",
            path="/api/v1/feedback",
            params=None,
            json_body={"kind": kind, "context": context},
        )
        if not response.get("ok"):
            return _json_response(response)
        result = response.get("result")
        if not isinstance(result, dict) or result.get("saved") is not True:
            raise ValueError("invalid backend response")
        return _json_response(
            {"ok": True, "action": "save_feedback", "result": {"saved": True}}
        )
    except ValueError:
        return _json_response(_error("invalid_arguments", "Feedback context is invalid."))
    except TrustedContextError:
        return _json_response(
            _error(
                "trusted_context_required",
                "Feedback is available only from a trusted Telegram session.",
            )
        )
    except RuntimeError:
        logger.error("Nails feedback plugin configuration is unavailable")
        return _json_response(
            _error("plugin_not_configured", "Feedback integration is not configured.")
        )
    except Exception:
        logger.exception("Unexpected Nails feedback tool failure")
        return _json_response(
            _error("internal_tool_error", "Feedback integration failed safely.")
        )
