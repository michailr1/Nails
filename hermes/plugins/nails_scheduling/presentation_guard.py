from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from typing import Any

from .portal import PORTAL_CONTINUE_URL

_MAX_PENDING_SESSIONS = 256
_MAX_TTL_SECONDS = 300
_PENDING: OrderedDict[str, tuple[str | None, str, float]] = OrderedDict()
_LOCK = threading.Lock()
_now = time.monotonic


def _clear_session(session_id: str) -> None:
    with _LOCK:
        _PENDING.pop(session_id, None)


def _parse_tool_result(result: Any) -> tuple[str, int] | None:
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (TypeError, ValueError):
            return None
    if not isinstance(result, dict) or result.get("ok") is not True:
        return None
    if result.get("action") != "approve":
        return None
    payload = result.get("result")
    if not isinstance(payload, dict) or payload.get("status") != "approved":
        return None
    login_url = payload.get("login_url")
    remaining_seconds = payload.get("remaining_seconds")
    if not isinstance(login_url, str) or not login_url.startswith(
        f"{PORTAL_CONTINUE_URL}?token="
    ):
        return None
    if not isinstance(remaining_seconds, int) or remaining_seconds <= 0:
        return None
    return login_url, remaining_seconds


def capture_web_login_result(
    *,
    tool_name: str,
    result: Any,
    session_id: str | None,
    turn_id: str | None = None,
    **_: Any,
) -> None:
    if tool_name != "web_login" or not isinstance(session_id, str) or not session_id:
        return None

    _clear_session(session_id)
    parsed = _parse_tool_result(result)
    if parsed is None:
        return None

    login_url, remaining_seconds = parsed
    expires_at = _now() + min(remaining_seconds, _MAX_TTL_SECONDS)
    with _LOCK:
        _PENDING[session_id] = (turn_id, login_url, expires_at)
        _PENDING.move_to_end(session_id)
        while len(_PENDING) > _MAX_PENDING_SESSIONS:
            _PENDING.popitem(last=False)
    return None


def enforce_login_url(
    *,
    response_text: str,
    session_id: str | None,
    platform: str | None = None,
    **_: Any,
) -> str | None:
    if not isinstance(session_id, str) or not session_id:
        return None

    with _LOCK:
        pending = _PENDING.pop(session_id, None)
    if pending is None:
        return None

    _turn_id, login_url, expires_at = pending
    if _now() > expires_at or platform != "telegram":
        return None
    if login_url in response_text:
        return None

    text = response_text.strip()
    if not text:
        return f"Вход подтверждён.\nОткрыть кабинет:\n{login_url}"
    return f"{text}\n\nОткрыть кабинет:\n{login_url}"


def _reset_for_tests() -> None:
    with _LOCK:
        _PENDING.clear()
