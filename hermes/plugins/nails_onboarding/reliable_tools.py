from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .tools import nails_onboarding as _raw_nails_onboarding

_STATE_REQUIRED_ACTIONS = {
    "save_master_name",
    "save_master_style",
    "save_default_work_hours",
    "save_section",
    "confirm_section",
    "pause",
    "resume",
    "complete",
}


def _decode(raw: str) -> dict[str, Any]:
    try:
        result = json.loads(raw)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "error": {
                "code": "invalid_tool_response",
                "message": "Onboarding integration returned an invalid response.",
            },
        }
    if not isinstance(result, dict):
        return {
            "ok": False,
            "error": {
                "code": "invalid_tool_response",
                "message": "Onboarding integration returned an invalid response.",
            },
        }
    return result


def _encode(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _error_code(result: dict[str, Any]) -> str | None:
    error = result.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if isinstance(code, str) else None


def _invoke(
    args: dict[str, Any],
    *,
    raw_tool: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    return _decode(raw_tool(args))


def nails_onboarding(args: dict[str, Any], **kwargs: Any) -> str:
    del kwargs

    action = args.get("action") if isinstance(args, dict) else None
    result = _invoke(args, raw_tool=_raw_nails_onboarding)

    if action not in _STATE_REQUIRED_ACTIONS:
        return _encode(result)
    if result.get("ok") is True:
        return _encode(result)
    if _error_code(result) != "onboarding_not_started":
        return _encode(result)

    started = _invoke({"action": "start"}, raw_tool=_raw_nails_onboarding)
    if started.get("ok") is not True:
        return _encode(started)

    retried = _invoke(args, raw_tool=_raw_nails_onboarding)
    return _encode(retried)
