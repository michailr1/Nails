from __future__ import annotations

import calendar
from datetime import date
from datetime import time as wall_time
from decimal import Decimal, InvalidOperation
from typing import Any

_ALLOWED_ACTIONS = {
    "cancel_booking",
    "create_booking",
    "create_client",
    "create_service",
    "day_view",
    "find_client",
    "find_client_candidates",
    "find_service",
    "free_slots",
    "list_services",
    "reschedule_booking",
    "resolve_date",
    "update_availability",
    "update_service",
}
_ALLOWED_DATE_KINDS = {"absolute", "month_day", "relative_days", "weekday"}
_ALLOWED_WEEKDAY_OCCURRENCES = {"nearest_future", "current_week", "next_week"}
_ALLOWED_MONTH_DAY_OCCURRENCES = {"nearest_future", "current_year", "next_year"}
_ALLOWED_AVAILABILITY_STATES = {"available", "unavailable", "unknown"}


class ToolInputError(ValueError):
    pass


def _text(value: Any, name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ToolInputError(f"{name} must be a string")
    result = " ".join(value.split())
    if not result or len(result) > maximum:
        raise ToolInputError(f"{name} is invalid")
    return result


def _optional_text(value: Any, name: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, name, maximum)


def _day(value: Any) -> str:
    try:
        return date.fromisoformat(_text(value, "day", 10)).isoformat()
    except ValueError as exc:
        raise ToolInputError("day must use YYYY-MM-DD format") from exc


def _time(value: Any, name: str = "start_time") -> str:
    try:
        parsed = wall_time.fromisoformat(_text(value, name, 8))
    except ValueError as exc:
        raise ToolInputError(f"{name} must use HH:MM format") from exc
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise ToolInputError(f"{name} must use local minute precision")
    return parsed.isoformat(timespec="minutes")


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolInputError(f"{name} is invalid")
    if not minimum <= value <= maximum:
        raise ToolInputError(f"{name} is invalid")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ToolInputError(f"{name} must be a boolean")
    return value


def _price(value: Any) -> str:
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


def _currency(value: Any) -> str:
    result = _text(value, "currency", 3).upper()
    if len(result) != 3 or not result.isascii() or not result.isalpha():
        raise ToolInputError("currency is invalid")
    return result


def _keys(args: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    if set(args) - allowed or not required.issubset(args):
        raise ToolInputError("invalid tool arguments")


def _confirmed(args: dict[str, Any]) -> None:
    if args.get("confirmed") is not True:
        raise ToolInputError("explicit confirmation is required")


def _date_resolution(args: dict[str, Any]) -> dict[str, Any]:
    kind = args.get("date_kind")
    if kind not in _ALLOWED_DATE_KINDS:
        raise ToolInputError("unsupported date resolution kind")
    if kind == "absolute":
        required = {"action", "date_kind", "day"}
        _keys(args, required, required)
        return {"kind": kind, "day": _day(args.get("day"))}
    if kind == "month_day":
        required = {"action", "date_kind", "month", "day_of_month", "occurrence"}
        _keys(args, required, required)
        month = _integer(args.get("month"), "month", 1, 12)
        maximum_day = calendar.monthrange(2000, month)[1]
        day_of_month = _integer(
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
        required = {"action", "date_kind", "offset_days"}
        _keys(args, required, required)
        return {
            "kind": kind,
            "offset_days": _integer(args.get("offset_days"), "offset_days", -366, 366),
        }
    required = {"action", "date_kind", "weekday_iso", "occurrence"}
    _keys(args, required, required)
    occurrence = args.get("occurrence")
    if occurrence not in _ALLOWED_WEEKDAY_OCCURRENCES:
        raise ToolInputError("weekday occurrence is invalid")
    return {
        "kind": kind,
        "weekday_iso": _integer(args.get("weekday_iso"), "weekday_iso", 1, 7),
        "occurrence": occurrence,
    }


def _service_values(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "service_name": _text(args.get("service_name"), "service_name", 160),
        "service_description": _optional_text(
            args.get("service_description"),
            "service_description",
            1000,
        ),
        "price_amount": _price(args.get("price_amount")),
        "currency": _currency(args.get("currency")),
        "duration_minutes": _integer(
            args.get("duration_minutes"),
            "duration_minutes",
            1,
            1440,
        ),
        "buffer_before_minutes": _integer(
            args.get("buffer_before_minutes"),
            "buffer_before_minutes",
            0,
            1440,
        ),
        "buffer_after_minutes": _integer(
            args.get("buffer_after_minutes"),
            "buffer_after_minutes",
            0,
            1440,
        ),
        "is_active": _boolean(args.get("is_active"), "is_active"),
    }


def _availability_days(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 31:
        raise ToolInputError("availability days are invalid")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ToolInputError("availability day is invalid")
        _keys(
            item,
            {"day", "state", "intervals", "note"},
            {"day", "state", "intervals"},
        )
        normalized_day = _day(item.get("day"))
        if normalized_day in seen:
            raise ToolInputError("availability days must be unique")
        seen.add(normalized_day)
        state = item.get("state")
        if state not in _ALLOWED_AVAILABILITY_STATES:
            raise ToolInputError("availability state is invalid")
        raw_intervals = item.get("intervals")
        if not isinstance(raw_intervals, list) or len(raw_intervals) > 4:
            raise ToolInputError("availability intervals are invalid")
        intervals = []
        for interval in raw_intervals:
            if not isinstance(interval, dict):
                raise ToolInputError("availability interval is invalid")
            if set(interval) != {"start_time", "end_time"}:
                raise ToolInputError("availability interval is invalid")
            start = _time(interval.get("start_time"), "start_time")
            end = _time(interval.get("end_time"), "end_time")
            if wall_time.fromisoformat(end) <= wall_time.fromisoformat(start):
                raise ToolInputError("availability interval end must be later than start")
            intervals.append({"start_time": start, "end_time": end})
        intervals.sort(key=lambda interval: interval["start_time"])
        if state == "available" and not intervals:
            raise ToolInputError("available day requires intervals")
        if state != "available" and intervals:
            raise ToolInputError("only available days may contain intervals")
        note = None
        if item.get("note") is not None:
            note = _text(item.get("note"), "note", 255)
        if state == "unknown" and note is not None:
            raise ToolInputError("unknown day cannot contain a note")
        result.append(
            {
                "day": normalized_day,
                "state": state,
                "intervals": intervals,
                "note": note,
            }
        )
    return sorted(result, key=lambda item: item["day"])


def _booking_values(args: dict[str, Any], *, include_new: bool) -> dict[str, Any]:
    allowed = {
        "action",
        "client_public_name",
        "service_name",
        "day",
        "start_time",
        "confirmed",
    }
    if include_new:
        allowed |= {"new_day", "new_start_time"}
    _keys(args, allowed, allowed)
    _confirmed(args)
    result = {
        "client_public_name": _text(
            args.get("client_public_name"),
            "client_public_name",
            160,
        ),
        "service_name": _text(args.get("service_name"), "service_name", 160),
        "day": _day(args.get("day")),
        "start_time": _time(args.get("start_time")),
    }
    if include_new:
        result["new_day"] = _day(args.get("new_day"))
        result["new_start_time"] = _time(
            args.get("new_start_time"),
            "new_start_time",
        )
    return result


def _validate_args(args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(args, dict):
        raise ToolInputError("tool arguments must be an object")
    action = args.get("action")
    if action not in _ALLOWED_ACTIONS:
        raise ToolInputError("unsupported scheduling action")
    if action == "resolve_date":
        return action, _date_resolution(args)
    if action == "list_services":
        _keys(args, {"action", "include_inactive"}, {"action"})
        include_inactive = _boolean(
            args.get("include_inactive", False),
            "include_inactive",
        )
        return action, {"include_inactive": include_inactive}
    if action == "find_service":
        required = {"action", "service_name"}
        _keys(args, required, required)
        return action, {
            "service_name": _text(args.get("service_name"), "service_name", 160)
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
        _keys(args, allowed, required)
        _confirmed(args)
        return action, _service_values(args)
    if action == "update_service":
        allowed = {"action", "confirmed", "current_service_name", *service_fields}
        required = allowed - {"service_description"}
        _keys(args, allowed, required)
        _confirmed(args)
        values = _service_values(args)
        values["current_service_name"] = _text(
            args.get("current_service_name"),
            "current_service_name",
            160,
        )
        return action, values
    if action == "day_view":
        required = {"action", "day"}
        _keys(args, required, required)
        return action, {"day": _day(args.get("day"))}
    if action == "free_slots":
        required = {"action", "day", "service_name"}
        _keys(args, required, required)
        return action, {
            "day": _day(args.get("day")),
            "service_name": _text(args.get("service_name"), "service_name", 160),
        }
    if action in {"find_client", "find_client_candidates"}:
        required = {"action", "client_public_name"}
        _keys(args, required, required)
        return action, {
            "client_public_name": _text(
                args.get("client_public_name"),
                "client_public_name",
                160,
            )
        }
    if action == "create_client":
        allowed = {"action", "client_public_name", "phone", "confirmed"}
        required = {"action", "client_public_name", "confirmed"}
        _keys(args, allowed, required)
        _confirmed(args)
        phone = None
        if args.get("phone") is not None:
            phone = _text(args.get("phone"), "phone", 32)
        return action, {
            "client_public_name": _text(
                args.get("client_public_name"),
                "client_public_name",
                160,
            ),
            "phone": phone,
        }
    if action == "update_availability":
        required = {"action", "days", "confirmed"}
        _keys(args, required, required)
        _confirmed(args)
        return action, {"days": _availability_days(args.get("days"))}
    if action == "create_booking":
        return action, _booking_values(args, include_new=False)
    if action == "reschedule_booking":
        return action, _booking_values(args, include_new=True)
    return action, _booking_values(args, include_new=False)


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
    if action == "find_client_candidates":
        return (
            "GET",
            "/api/v1/scheduling/clients/candidates",
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
    if action in {
        "cancel_booking",
        "create_booking",
        "create_client",
        "reschedule_booking",
    }:
        raise ToolInputError(f"{action} requires the guarded write flow")
    raise ToolInputError("unsupported scheduling action")
