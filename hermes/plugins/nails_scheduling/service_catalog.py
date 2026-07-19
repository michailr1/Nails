from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .validation import ToolInputError

_SERVICE_KINDS = {"base", "addon"}
_PRICE_TYPES = {"fixed", "range", "per_unit", "on_request"}
_SERVICE_FIELDS = {
    "service_name",
    "service_description",
    "price_amount",
    "currency",
    "duration_minutes",
    "buffer_before_minutes",
    "buffer_after_minutes",
    "is_active",
    "kind",
    "price_type",
    "price_min_amount",
    "price_max_amount",
    "price_unit",
    "category",
    "sort_order",
    "extra_minutes",
}


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


def _money(value: Any, name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ToolInputError(f"{name} is invalid")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ToolInputError(f"{name} is invalid") from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
        raise ToolInputError(f"{name} is invalid")
    if amount.as_tuple().exponent < -2:
        raise ToolInputError(f"{name} must have at most two decimal places")
    return f"{amount:.2f}"


def _optional_money(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _money(value, name)


def _currency(value: Any) -> str:
    result = _text(value, "currency", 3).upper()
    if len(result) != 3 or not result.isascii() or not result.isalpha():
        raise ToolInputError("currency is invalid")
    return result


def validate_service_catalog_args(args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    action = args.get("action")
    if action not in {"create_service", "update_service"}:
        raise ToolInputError("unsupported service catalog action")

    allowed = {"action", "confirmed", *_SERVICE_FIELDS}
    if action == "update_service":
        allowed.add("current_service_name")
    if set(args) - allowed:
        raise ToolInputError("invalid tool arguments")
    if args.get("confirmed") is not True:
        raise ToolInputError("explicit confirmation is required")

    kind = args.get("kind", "base")
    if kind not in _SERVICE_KINDS:
        raise ToolInputError("kind is invalid")
    price_type = args.get("price_type")
    if price_type is None:
        price_type = "fixed" if args.get("price_amount") is not None else "on_request"
    if price_type not in _PRICE_TYPES:
        raise ToolInputError("price_type is invalid")

    price_amount = _optional_money(args.get("price_amount"), "price_amount")
    price_min_amount = _optional_money(args.get("price_min_amount"), "price_min_amount")
    price_max_amount = _optional_money(args.get("price_max_amount"), "price_max_amount")
    price_unit = _optional_text(args.get("price_unit"), "price_unit", 80)

    if price_type == "fixed":
        if price_amount is None or any(
            value is not None for value in (price_min_amount, price_max_amount, price_unit)
        ):
            raise ToolInputError("fixed price shape is invalid")
    elif price_type == "range":
        if price_min_amount is None or price_max_amount is None:
            raise ToolInputError("range price shape is invalid")
        if Decimal(price_max_amount) < Decimal(price_min_amount):
            raise ToolInputError("range price shape is invalid")
        if price_amount is not None or price_unit is not None:
            raise ToolInputError("range price shape is invalid")
    elif price_type == "per_unit":
        if price_amount is None or price_unit is None:
            raise ToolInputError("per_unit price shape is invalid")
        if price_min_amount is not None or price_max_amount is not None:
            raise ToolInputError("per_unit price shape is invalid")
    elif any(
        value is not None
        for value in (price_amount, price_min_amount, price_max_amount, price_unit)
    ):
        raise ToolInputError("on_request price shape is invalid")

    duration = args.get("duration_minutes")
    extra_minutes = _integer(args.get("extra_minutes", 0), "extra_minutes", 0, 1440)
    if kind == "base":
        duration = _integer(duration, "duration_minutes", 1, 1440)
        if extra_minutes != 0:
            raise ToolInputError("base service cannot have extra_minutes")
    else:
        if duration is not None:
            raise ToolInputError("addon cannot have duration_minutes")
        duration = None

    values = {
        "service_name": _text(args.get("service_name"), "service_name", 160),
        "service_description": _optional_text(
            args.get("service_description"),
            "service_description",
            1000,
        ),
        "price_amount": price_amount,
        "currency": _currency(args.get("currency", "RUB")),
        "duration_minutes": duration,
        "buffer_before_minutes": _integer(
            args.get("buffer_before_minutes", 0),
            "buffer_before_minutes",
            0,
            1440,
        ),
        "buffer_after_minutes": _integer(
            args.get("buffer_after_minutes", 0),
            "buffer_after_minutes",
            0,
            1440,
        ),
        "is_active": _boolean(args.get("is_active", True), "is_active"),
        "kind": kind,
        "price_type": price_type,
        "price_min_amount": price_min_amount,
        "price_max_amount": price_max_amount,
        "price_unit": price_unit,
        "category": _optional_text(args.get("category"), "category", 160),
        "sort_order": _integer(args.get("sort_order", 0), "sort_order", 0, 1_000_000),
        "extra_minutes": extra_minutes,
    }
    if action == "update_service":
        values["current_service_name"] = _text(
            args.get("current_service_name"),
            "current_service_name",
            160,
        )
    return action, values


def service_catalog_request_spec(
    action: str,
    values: dict[str, Any],
) -> tuple[str, str, None, dict[str, Any]]:
    body = {
        "public_name": values["service_name"],
        "public_description": values["service_description"],
        "price_amount": values["price_amount"],
        "currency": values["currency"],
        "duration_minutes": values["duration_minutes"],
        "buffer_before_minutes": values["buffer_before_minutes"],
        "buffer_after_minutes": values["buffer_after_minutes"],
        "is_active": values["is_active"],
        "kind": values["kind"],
        "price_type": values["price_type"],
        "price_min_amount": values["price_min_amount"],
        "price_max_amount": values["price_max_amount"],
        "price_unit": values["price_unit"],
        "category": values["category"],
        "sort_order": values["sort_order"],
        "extra_minutes": values["extra_minutes"],
    }
    if action == "create_service":
        return "POST", "/api/v1/scheduling/services", None, body
    body["current_public_name"] = values["current_service_name"]
    return "PUT", "/api/v1/scheduling/services", None, body
