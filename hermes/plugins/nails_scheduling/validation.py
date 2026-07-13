from __future__ import annotations

from datetime import date
from datetime import time as wall_time
from typing import Any

_ALLOWED_ACTIONS = {
    "list_services",
    "day_view",
    "free_slots",
    "find_client",
    "create_client",
    "create_booking",
}


class ToolInputError(ValueError):
    pass


def _normalize_text(value: Any, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ToolInputError(f"{field_name} must be a string")
    candidate = " ".join(value.split())
    if not candidate or len(candidate) > max_length:
        raise ToolInputError(f"{field_name} is invalid")
    return candidate


def _normalize_day(value: Any) -> str:
    if not isinstance(value, str):
        raise ToolInputError("day must be a date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ToolInputError("day must use YYYY-MM-DD format") from exc
    return parsed.isoformat()


def _normalize_start_time(value: Any) -> str:
    if not isinstance(value, str):
        raise ToolInputError("start_time must be a time string")
    try:
        parsed = wall_time.fromisoformat(value)
    except ValueError as exc:
        raise ToolInputError("start_time must use HH:MM format") from exc
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise ToolInputError("start_time must use local minute precision")
    return parsed.isoformat(timespec="minutes")


def _normalize_phone(value: Any) -> str | None:
    if value is None:
        return None
    return _normalize_text(value, "phone", 32)


def _require_exact_keys(
    args: dict[str, Any],
    allowed: set[str],
    required: set[str],
) -> None:
    if set(args) - allowed:
        raise ToolInputError("unsupported tool arguments")
    if not required.issubset(args):
        raise ToolInputError("required tool arguments are missing")


def _validate_args(args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(args, dict):
        raise ToolInputError("tool arguments must be an object")
    action = args.get("action")
    if action not in _ALLOWED_ACTIONS:
        raise ToolInputError("unsupported scheduling action")

    if action == "list_services":
        _require_exact_keys(args, {"action"}, {"action"})
        return action, {}

    if action == "day_view":
        _require_exact_keys(args, {"action", "day"}, {"action", "day"})
        return action, {"day": _normalize_day(args.get("day"))}

    if action == "free_slots":
        _require_exact_keys(
            args,
            {"action", "day", "service_name"},
            {"action", "day", "service_name"},
        )
        return action, {
            "day": _normalize_day(args.get("day")),
            "service_name": _normalize_text(
                args.get("service_name"),
                "service_name",
                160,
            ),
        }

    if action == "find_client":
        _require_exact_keys(
            args,
            {"action", "client_public_name"},
            {"action", "client_public_name"},
        )
        return action, {
            "client_public_name": _normalize_text(
                args.get("client_public_name"),
                "client_public_name",
                160,
            )
        }

    if action == "create_client":
        _require_exact_keys(
            args,
            {"action", "client_public_name", "phone", "confirmed"},
            {"action", "client_public_name", "confirmed"},
        )
        if args.get("confirmed") is not True:
            raise ToolInputError("explicit confirmation is required")
        return action, {
            "client_public_name": _normalize_text(
                args.get("client_public_name"),
                "client_public_name",
                160,
            ),
            "phone": _normalize_phone(args.get("phone")),
        }

    _require_exact_keys(
        args,
        {
            "action",
            "client_public_name",
            "service_name",
            "day",
            "start_time",
            "confirmed",
        },
        {
            "action",
            "client_public_name",
            "service_name",
            "day",
            "start_time",
            "confirmed",
        },
    )
    if args.get("confirmed") is not True:
        raise ToolInputError("explicit confirmation is required")
    return action, {
        "client_public_name": _normalize_text(
            args.get("client_public_name"),
            "client_public_name",
            160,
        ),
        "service_name": _normalize_text(
            args.get("service_name"),
            "service_name",
            160,
        ),
        "day": _normalize_day(args.get("day")),
        "start_time": _normalize_start_time(args.get("start_time")),
    }


def _request_spec(
    action: str,
    values: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
    if action == "list_services":
        return "GET", "/api/v1/scheduling/services", None, None
    if action == "day_view":
        return "GET", "/api/v1/scheduling/day", {"day": values["day"]}, None
    if action == "free_slots":
        return (
            "GET",
            "/api/v1/scheduling/slots",
            {"day": values["day"], "service_name": values["service_name"]},
            None,
        )
    if action == "find_client":
        return (
            "GET",
            "/api/v1/scheduling/clients/exact",
            {"public_name": values["client_public_name"]},
            None,
        )
    if action in {"create_client", "create_booking"}:
        raise ToolInputError(f"{action} requires the guarded write flow")
    raise ToolInputError("unsupported scheduling action")
