from __future__ import annotations

from typing import Any

from .service_catalog import validate_service_catalog_args
from .validation import ToolInputError

_MAX_SERVICES = 200


def validate_replace_catalog_args(args: dict[str, Any]) -> dict[str, Any]:
    if set(args) != {"action", "services", "confirmed"}:
        raise ToolInputError("invalid tool arguments")
    if args.get("confirmed") is not True:
        raise ToolInputError("explicit confirmation is required")
    services = args.get("services")
    if not isinstance(services, list) or not 1 <= len(services) <= _MAX_SERVICES:
        raise ToolInputError("services must contain between 1 and 200 items")

    validated: list[dict[str, Any]] = []
    normalized_names: set[str] = set()
    for item in services:
        if not isinstance(item, dict):
            raise ToolInputError("catalog item must be an object")
        _, values = validate_service_catalog_args(
            {
                "action": "create_service",
                "confirmed": True,
                "currency": "RUB",
                "buffer_before_minutes": 0,
                "buffer_after_minutes": 0,
                "is_active": True,
                **item,
            }
        )
        normalized_name = values["service_name"].casefold()
        if normalized_name in normalized_names:
            raise ToolInputError("catalog service names must be unique")
        normalized_names.add(normalized_name)
        validated.append(values)
    return {"services": validated}


def replace_catalog_request_body(values: dict[str, Any]) -> dict[str, Any]:
    services: list[dict[str, Any]] = []
    for item in values["services"]:
        service = {
            "public_name": item["service_name"],
            "public_description": item["service_description"],
            "price_amount": item["price_amount"],
            "currency": item["currency"],
            "duration_minutes": item["duration_minutes"],
            "buffer_before_minutes": item["buffer_before_minutes"],
            "buffer_after_minutes": item["buffer_after_minutes"],
            "is_active": True,
            "kind": item["kind"],
            "price_type": item["price_type"],
            "price_min_amount": item["price_min_amount"],
            "price_max_amount": item["price_max_amount"],
            "price_unit": item["price_unit"],
            "category": item["category"],
            "sort_order": item["sort_order"],
            "extra_minutes": item["extra_minutes"],
        }
        services.append(service)
    return {"services": services}
