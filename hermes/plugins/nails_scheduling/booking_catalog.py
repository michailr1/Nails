from __future__ import annotations

from typing import Any

from .validation import (
    ToolInputError,
    _confirmed,
    _day,
    _integer,
    _keys,
    _price,
    _text,
    _time,
)


def _addon_names(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise ToolInputError("addon_names is invalid")

    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        name = _text(item, "addon_name", 160)
        key = name.casefold()
        if key in seen:
            raise ToolInputError("addon_names must be unique")
        seen.add(key)
        result.append(name)
    return result


def validate_catalog_booking_args(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "action",
        "client_public_name",
        "service_name",
        "addon_names",
        "day",
        "start_time",
        "price_override_amount",
        "duration_override_minutes",
        "confirmed",
    }
    required = {
        "action",
        "client_public_name",
        "service_name",
        "day",
        "start_time",
        "confirmed",
    }
    _keys(args, allowed, required)
    _confirmed(args)

    service_name = _text(args.get("service_name"), "service_name", 160)
    addons = _addon_names(args.get("addon_names"))
    if any(addon.casefold() == service_name.casefold() for addon in addons):
        raise ToolInputError("base service cannot also be an addon")

    price_override = None
    if args.get("price_override_amount") is not None:
        price_override = _price(args.get("price_override_amount"))

    duration_override = None
    if args.get("duration_override_minutes") is not None:
        duration_override = _integer(
            args.get("duration_override_minutes"),
            "duration_override_minutes",
            1,
            1440,
        )

    return {
        "client_public_name": _text(
            args.get("client_public_name"),
            "client_public_name",
            160,
        ),
        "service_name": service_name,
        "addon_names": addons,
        "day": _day(args.get("day")),
        "start_time": _time(args.get("start_time")),
        "price_override_amount": price_override,
        "duration_override_minutes": duration_override,
    }
