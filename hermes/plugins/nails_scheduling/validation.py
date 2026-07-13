from __future__ import annotations

from datetime import date
from datetime import time as wall_time
from typing import Any

_ALLOWED_ACTIONS = {
    "resolve_date",
    "list_services",
    "day_view",
    "free_slots",
    "find_client",
    "create_client",
    "update_availability",
    "create_booking",
}
_ALLOWED_DATE_KINDS = {"absolute", "relative_days", "weekday"}
_ALLOWED_OCCURRENCES = {"nearest_future", "current_week", "next_week"}
_ALLOWED_AVAILABILITY_STATES = {"available", "unavailable", "unknown"}


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


def _normalize_note(value: Any) -> str | None:
    if value is None:
        return None
    return _normalize_text(value, "note", 255)


def _require_exact_keys(
    args: dict[str, Any],
    allowed: set[str],
    required: set[str],
) -> None:
    if set(args) - allowed:
        raise ToolInputError("unsupported tool arguments")
    if not required.issubset(args):
        raise ToolInputError("required tool arguments are missing")


def _normalize_date_resolution(args: dict[str, Any]) -> dict[str, Any]:
    kind = args.get("date_kind")
    if kind not in _ALLOWED_DATE_KINDS:
        raise ToolInputError("unsupported date resolution kind")
    if kind == "absolute":
        _require_exact_keys(args, {"action", "date_kind", "day"}, {"action", "date_kind", "day"})
        return {"kind": kind, "day": _normalize_day(args.get("day"))}
    if kind == "relative_days":
        _require_exact_keys(
            args,
            {"action", "date_kind", "offset_days"},
            {"action", "date_kind", "offset_days"},
        )
        offset = args.get("offset_days")
        if isinstance(offset, bool) or not isinstance(offset, int) or not -366 <= offset <= 366:
            raise ToolInputError("offset_days is invalid")
        return {"kind": kind, "offset_days": offset}

    _require_exact_keys(
        args,
        {"action", "date_kind", "weekday_iso", "occurrence"},
        {"action", "date_kind", "weekday_iso", "occurrence"},
    )
    weekday_iso = args.get("weekday_iso")
    occurrence = args.get("occurrence")
    if isinstance(weekday_iso, bool) or not isinstance(weekday_iso, int) or not 1 <= weekday_iso <= 7:
        raise ToolInputError("weekday_iso is invalid")
    if occurrence not in _ALLOWED_OCCURRENCES:
        raise ToolInputError("occurrence is invalid")
    return {
        "kind": kind,
        "weekday_iso": weekday_iso,
        "occurrence": occurrence,
    }


def _normalize_availability_days(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 31:
        raise ToolInputError("availability days are invalid")

    normalized: list[dict[str, Any]] = []
    seen_days: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ToolInputError("availability day is invalid")
        if set(item) - {"day", "state", "intervals", "note"}:
            raise ToolInputError("unsupported availability day fields")
        if not {"day", "state", "intervals"}.issubset(item):
            raise ToolInputError("availability day fields are missing")

        day = _normalize_day(item.get("day"))
        if day in seen_days:
            raise ToolInputError("availability days must be unique")
        seen_days.add(day)

        state = item.get("state")
        if state not in _ALLOWED_AVAILABILITY_STATES:
            raise ToolInputError("availability state is invalid")
        intervals_value = item.get("intervals")
        if not isinstance(intervals_value, list) or len(intervals_value) > 4:
            raise ToolInputError("availability intervals are invalid")

        intervals: list[tuple[wall_time, wall_time]] = []
        for interval in intervals_value:
            if not isinstance(interval, dict) or set(interval) != {"start_time", "end_time"}:
                raise ToolInputError("availability interval is invalid")
            start = wall_time.fromisoformat(_normalize_start_time(interval.get("start_time")))
            end = wall_time.fromisoformat(_normalize_start_time(interval.get("end_time")))
            if end <= start:
                raise ToolInputError("availability interval end must be later than start")
            intervals.append((start, end))
        intervals.sort(key=lambda pair: pair[0])
        for previous, current in zip(intervals, intervals[1:], strict=False):
            if current[0] < previous[1]:
                raise ToolInputError("availability intervals must not overlap")

        note = _normalize_note(item.get("note"))
        if state == "available" and not intervals:
            raise ToolInputError("available day requires intervals")
        if state != "available" and intervals:
            raise ToolInputError("only available days may contain intervals")
        if state == "unknown" and note is not None:
            raise ToolInputError("unknown day cannot contain a note")

        normalized.append(
            {
                "day": day,
                "state": state,
                "intervals": [
                    {
                        "start_time": start.isoformat(timespec="minutes"),
                        "end_time": end.isoformat(timespec="minutes"),
                    }
                    for start, end in intervals
                ],
                "note": note,
            }
        )

    normalized.sort(key=lambda item: item["day"])
    return normalized


def _validate_args(args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(args, dict):
        raise ToolInputError("tool arguments must be an object")
    action = args.get("action")
    if action not in _ALLOWED_ACTIONS:
        raise ToolInputError("unsupported scheduling action")

    if action == "resolve_date":
        return action, _normalize_date_resolution(args)

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
            "service_name": _normalize_text(args.get("service_name"), "service_name", 160),
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

    if action == "update_availability":
        _require_exact_keys(
            args,
            {"action", "days", "confirmed"},
            {"action", "days", "confirmed"},
        )
        if args.get("confirmed") is not True:
            raise ToolInputError("explicit confirmation is required")
        return action, {"days": _normalize_availability_days(args.get("days"))}

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
        "service_name": _normalize_text(args.get("service_name"), "service_name", 160),
        "day": _normalize_day(args.get("day")),
        "start_time": _normalize_start_time(args.get("start_time")),
    }


def _request_spec(
    action: str,
    values: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
    if action == "resolve_date":
        return "POST", "/api/v1/scheduling/date/resolve", None, values
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
    if action == "update_availability":
        return "PUT", "/api/v1/scheduling/availability", None, {"days": values["days"]}
    if action in {"create_client", "create_booking"}:
        raise ToolInputError(f"{action} requires the guarded write flow")
    raise ToolInputError("unsupported scheduling action")
