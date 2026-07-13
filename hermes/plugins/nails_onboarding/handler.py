from __future__ import annotations

import json
from typing import Any

from .guidance import build_dialogue_guidance
from .tools import nails_onboarding as _nails_onboarding


def nails_onboarding(args: dict[str, Any], **kwargs: Any) -> str:
    """Call the restricted tool and attach deterministic dialogue guidance."""

    raw = _nails_onboarding(args, **kwargs)

    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return raw

    result = payload.get("result")
    if not isinstance(result, dict):
        return raw

    if "current_step" not in result or "sections" not in result:
        return raw

    result["dialogue_guidance"] = build_dialogue_guidance(result)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
