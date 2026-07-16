from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from .tools import (
    TrustedContextError,
    _api_key,
    _json_response,
    _trusted_telegram_user_id,
)
from .transport import _call_backend, _error

logger = logging.getLogger(__name__)
_ALLOWED_KINDS = {"thumbs_down", "unrecognized"}
_ALLOWED_ROLES = {"user", "assistant"}
_MAX_NOTIFICATION_LENGTH = 3500


def _validate(args: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(args, dict) or set(args) != {"kind", "context"}:
        raise ValueError("invalid arguments")

    kind = args.get("kind")
    context = args.get("context")
    if kind not in _ALLOWED_KINDS:
        raise ValueError("invalid kind")
    if not isinstance(context, list) or not 1 <= len(context) <= 4:
        raise ValueError("invalid context")

    validated: list[dict[str, str]] = []
    for item in context:
        if not isinstance(item, dict) or set(item) != {"role", "text"}:
            raise ValueError("invalid message")
        role = item.get("role")
        text = item.get("text")
        if role not in _ALLOWED_ROLES:
            raise ValueError("invalid role")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
            raise ValueError("invalid text")
        validated.append({"role": role, "text": text.strip()})

    return kind, validated


def _validated_safe_context(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 4:
        raise ValueError("invalid safe context")
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"role", "text"}:
            raise ValueError("invalid safe context message")
        role = item.get("role")
        text = item.get("text")
        if role not in _ALLOWED_ROLES:
            raise ValueError("invalid safe context role")
        if not isinstance(text, str) or not 1 <= len(text) <= 1000:
            raise ValueError("invalid safe context text")
        result.append({"role": role, "text": text})
    return result


def _notification_text(kind: str, context: list[dict[str, str]]) -> str:
    kind_label = "неудачный ответ" if kind == "thumbs_down" else "нераспознанный запрос"
    lines = ["👎 Отзыв о Нэйли", f"Тип: {kind_label}", "", "Контекст:"]
    for message in context:
        author = "Мастер" if message["role"] == "user" else "Нэйли"
        lines.append(f"{author}: {message['text']}")
    return "\n".join(lines)[:_MAX_NOTIFICATION_LENGTH]


def _notify_admin(kind: str, context: list[dict[str, str]]) -> bool:
    token = (
        os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        or os.getenv("TELEGRAM_TOKEN", "").strip()
    )
    chat_id = os.getenv("NAILS_BACKUP_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logger.warning("Feedback saved but admin Telegram notification is not configured")
        return False

    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": _notification_text(kind, context),
                "disable_web_page_preview": True,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise ValueError("Telegram rejected notification")
    except (httpx.HTTPError, ValueError):
        logger.warning("Feedback saved but admin Telegram notification failed")
        return False
    return True


def save_feedback(args: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        kind, context = _validate(args)
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
            return _json_response(
                _error(
                    "invalid_backend_response",
                    "Feedback service returned an invalid response.",
                )
            )
        safe_context = _validated_safe_context(result.get("safe_context"))
        admin_notified = _notify_admin(kind, safe_context)
        return _json_response(
            {
                "ok": True,
                "action": "save_feedback",
                "result": {"saved": True, "admin_notified": admin_notified},
            }
        )
    except ValueError:
        return _json_response(
            _error("invalid_arguments", "The feedback tool received invalid arguments.")
        )
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
        logger.exception("Unexpected Nails feedback plugin failure")
        return _json_response(
            _error("internal_tool_error", "Feedback integration failed safely.")
        )
