from __future__ import annotations

import calendar
from datetime import date
from datetime import time as wall_time
from decimal import Decimal, InvalidOperation
from typing import Any

_ALLOWED_ACTIONS = {
    "resolve_date",
    "list_services",
    "find_service",
    "create_service",
    "update_service",
    "day_view",
    "free_slots",
    "find_client",
    "create_client",
    "update_availability",
    "create_booking",
}
_ALLOWED_DATE_KINDS = {"absolute", "month_day", "relative_days", "weekday"}
_ALLOWED_WEEKDAY_OCCURRENCES = {"nearest_future", "current_week", "next_week"}
_ALLOWED_MONTH_DAY_OCCURRENCES = {"nearest_future", "current_year", "next_year"}
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


def _normalize_optional_text(value: Any, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolInputError(f"{field_name} must be a string or null")
    candidate = " ".join(value.split())
    if len(candidate) > max_length:
        raise ToolInputError(f"{field_name} is invalid")
    return candidate or None


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


def _bounded_int(value: Any, field_name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolInputError(f"{field_name} is invalid")
    if not minimum <= value <= maximum:
        raise ToolInputError(f"{field_name} is invalid")
    return value


def _normalize_price(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ToolInputError("price_amount is invalid")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ToolInputError("price_amount is invalid") from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
        raise ToolInputError("price_amount is invalid")
    if amount.as_tuple().exponent < -2:
        raise ToolInputError("price_amount must have at most two decimal places")
    return f"{amount:.2f}"


def _normalize_currency(value: Any) -> str:
    currency = _normalize_text(value, "currency", 3).upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise ToolInputError("currency is invalid")
    return currency


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ToolInputError(f"{field_name} must be a boolean")
    return value


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
        keys = {"action", "date_kind", "day"}
        _require_exact_keys(args, keys, keys)
        return {"kind": kind, "day": _normalize_day(args.get("day"))}

    if kind == "month_day":
        keys = {"action", "date_kind", "month", "day_of_month", "occurrence"}
        _require_exact_keys(args, keys, keys)
        month = _bounded_int(args.get("month"), "month", 1, 12)
        maximum_day = calendar.monthrange(2000, month)[1]
        day_of_month = _bounded_int(
            args.get("day_of_month"),
            "day_of_month",
            1,
            maximum_day,
        )
        occurrence = args.get("occurrence")
        if occurrence not in _ALLOWED_MONTH_DAY_OCCURRENCES:
            raise ToolInputError("month-day occurrence is invalid")
        return {
            "kind": kind,
            "month": month,
            "day_of_month": day_of_month,
            "occurrence": occurrence,
        }

    if kind == "relative_days":
        keys = {"action", "date_kind", "offset_days"}
        _require_exact_keys(args, keys, keys)
        offset = _bounded_int(args.get("offset_days"), "offset_days", -366, 366)
        return {"kind": kind, "offset_days": offset}

    keys = {"action", "date_kind", "weekday_iso", "occurrence"}
    _require_exact_keys(args, keys, keys)
    weekday_iso = _bounded_int(args.get("weekday_iso"), "weekday_iso", 1, 7)
    occurrence = args.get("occurrence")
    if occurrence not in _ALLOWED_WEEKDAY_OCCURRENCES:
        raise ToolInputError("weekday occurrence is invalid")
    return {
        "kind": kind,
        "weekday_iso": weekday_iso,
        "occurrence": occurrence,
    }


def _normalize_service_values(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "service_name": _normalize_text(args.get("service_name"), "service_name", 160),
        "service_description": _normalize_optional_text(
            args.get("service_description"),
            "service_description",
            1000,
        ),
        "price_amount": _normalize_price(args.get("price_amount")),
        "currency": _normalize_currency(args.get("currency")),
        "duration_minutes": _bounded_int(
            args.get("duration_minutes"),
            "duration_minutes",
            1,
            1440,
        ),
        "buffer_before_minutes": _bounded_int(
            args.get("buffer_before_minutes"),
            "buffer_before_minutes",
            0,
            1440,
        ),
        "buffer_after_minutes": _bounded_int(
            args.get("buffer_after_minutes"),
            "buffer_after_minutes",
            0,
            1440,
        ),
        "is_active": _require_bool(args.get("is_active"), "is_active"),
    }


def _normalize_intervals(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > 4:
        raise ToolInputError("availability intervals are invalid")

    intervals: list[tuple[wall_time, wall_time]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ToolInputError("availability interval is invalid")
        if set(item) != {"start_time", "end_time"}:
            raise ToolInputError("availability interval is invalid")
        start = wall_time.fromisoformat(_normalize_start_time(item.get("start_time")))
        end = wall_time.fromisoformat(_normalize_start_time(item.get("end_time")))
        if end <= start:
            raise ToolInputError("availability interval end must be later than start")
        intervals.append((start, end))

    intervals.sort(key=lambda pair: pair[0])
    for previous, current in zip(intervals, intervals[1:], strict=False):
        if current[0] < previous[1]:
            raise ToolInputError("availability intervals must not overlap")

    return [
        {
            "start_time": start.isoformat(timespec="minutes"),
            "end_time": end.isoformat(timespec="minutes"),
        }
        for start, end in intervals
    ]


def _normalize_availability_days(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 31:
        raise ToolInputError("availability days are invalid")

    normalized: list[dict[str, Any]] = []
    seen_days: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ToolInputError("availability day is invalid")
        allowed = {"day", "state", "intervals", "note"}
        required = {"day", "state", "intervals"}
        _require_exact_keys(item, allowed, required)

        day = _normalize_day(item.get("day"))
        if day in seen_days:
            raise ToolInputError("availability days must be unique")
        seen_days.add(day)

        state = item.get("state")
        if state not in _ALLOWED_AVAILABILITY_STATES:
            raise ToolInputError("availability state is invalid")
        intervals = _normalize_intervals(item.get("intervals"))
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
                "intervals": intervals,
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
        allowed = {"action", "include_inactive"}
        _require_exact_keys(args, allowed, {"action"})
        include_inactive = args.get("include_inactive", False)
        return action, {
            "include_inactive": _require_bool(include_inactive, "include_inactive")
        }

    if action == "find_service":
        allowed = {"action", "service_name"}
        _require_exact_keys(args, allowed, allowed)
        return action, {
            "service_name": _normalize_text(args.get("service_name"), "service_name", 160)
        }

    service_fields = {
        "service_name",
        "service_description",
        "price_amount",
        "currency",
        "duration_minutes",
        "buffer_before_minutes",
        "buffer_after_minutes",
        "is_active",
    }
    if action == "create_service":
        allowed = {"action", "confirmed", *service_fields}
        required = allowed - {"service_description"}
        _require_exact_keys(args, allowed, required)
        if args.get("confirmed") is not True:
            raise ToolInputError("explicit confirmation is required")
        return action, _normalize_service_values(args)

    if action == "update_service":
        allowed = {"action", "confirmed", "current_service_name", *service_fields}
        required = allowed - {"service_description"}
        _require_exact_keys(args, allowed, required)
        if args.get("confirmed") is not True:
            raise ToolInputError("explicit confirmation is required")
        values = _normalize_service_values(args)
        values["current_service_name"] = _normalize_text(
            args.get("current_service_name"),
            "current_service_name",
            160,
        )
        return action, values

    if action == "day_view":
        _require_exact_keys(args, {"action", "day"}, {"action", "day"})
        return action, {"day": _normalize_day(args.get("day"))}

    if action == "free_slots":
        allowed = {"action", "day", "service_name"}
        _require_exact_keys(args, allowed, allowed)
        return action, {
            "day": _normalize_day(args.get("day")),
            "service_name": _normalize_text(
                args.get("service_name"),
                "service_name",
                160,
            ),
        }

    if action == "find_client":
        allowed = {"action", "client_public_name"}
        _require_exact_keys(args, allowed, allowed)
        return action, {
            "client_public_name": _normalize_text(
                args.get("client_public_name"),
                "client_public_name",
                160,
            )
        }

    if action == "create_client":
        allowed = {"action", "client_public_name", "phone", "confirmed"}
        required = {"action", "client_public_name", "confirmed"}
        _require_exact_keys(args, allowed, required)
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
        allowed = {"action", "days", "confirmed"}
        _require_exact_keys(args, allowed, allowed)
        if args.get("confirmed") is not True:
            raise ToolInputError("explicit confirmation is required")
        return action, {"days": _normalize_availability_days(args.get("days"))}

    allowed = {
        "action",
        "client_public_name",
        "service_name",
        "day",
        "start_time",
        "confirmed",
    }
    _require_exact_keys(args, allowed, allowed)
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


def _service_json(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "public_name": values["service_name"],
        "public_description": values["service_description"],
        "price_amount": values["price_amount"],
        "currency": values["currency"],
        "duration_minutes": values["duration_minutes"],
        "buffer_before_minutes": values["buffer_before_minutes"],
        "buffer_after_minutes": values["buffer_after_minutes"],
        "is_active": values["is_active"],
    }


def _request_spec(
    action: str,
    values: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
    if action == "resolve_date":
        return "POST", "/api/v1/scheduling/date/resolve", None, values
    if action == "list_services":
        return (
            "GET",
            "/api/v1/scheduling/services",
            {"include_inactive": str(values["include_inactive"]).lower()},
            None,
        )
    if action == "find_service":
        return (
            "GET",
            "/api/v1/scheduling/services/exact",
            {"public_name": values["service_name"]},
            None,
        )
    if action == "create_service":
        return "POST", "/api/v1/scheduling/services", None, _service_json(values)
    if action == "update_service":
        body = _service_json(values)
        body["current_public_name"] = values["current_service_name"]
        return "PUT", "/api/v1/scheduling/services", None, body
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
        return (
            "PUT",
            "/api/v1/scheduling/availability",
            None,
            {"days": values["days"]},
        )
    if action in {"create_client", "create_booking"}:
        raise ToolInputError(f"{action} requires the guarded write flow")
    raise ToolInputError("unsupported scheduling action")
