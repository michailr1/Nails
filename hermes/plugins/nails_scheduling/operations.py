from __future__ import annotations

from datetime import date, datetime
from datetime import time as wall_time
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .presenters import _normalized_lookup, _parse_backend_datetime
from .transport import _call_backend, _error


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc


def _booking_addon_quantities(booking: dict[str, Any]) -> dict[str, int]:
    items = booking.get("catalog_items")
    if not isinstance(items, list):
        return {}
    result: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict) or item.get("kind") != "addon":
            continue
        name = item.get("public_name")
        if not isinstance(name, str):
            continue
        quantity = item.get("quantity", 1)
        if not isinstance(quantity, int) or quantity < 1:
            quantity = 1
        result[_normalized_lookup(name)] = quantity
    return result


def _matching_existing_booking(
    day_result: dict[str, Any],
    *,
    client_public_name: str,
    service_name: str,
    starts_at: datetime,
    addon_names: list[str] | None = None,
    addon_quantities: dict[str, int] | None = None,
    price_override_amount: str | None = None,
    duration_override_minutes: int | None = None,
) -> dict[str, Any] | None:
    bookings = day_result.get("bookings")
    if not isinstance(bookings, list):
        raise ValueError("invalid day bookings")
    matches = []
    for booking in bookings:
        if not isinstance(booking, dict):
            continue
        if _normalized_lookup(str(booking.get("client_public_name", ""))) != _normalized_lookup(
            client_public_name
        ):
            continue
        if _normalized_lookup(str(booking.get("service_name", ""))) != _normalized_lookup(
            service_name
        ):
            continue
        try:
            existing_start = _parse_backend_datetime(booking.get("starts_at"))
        except ValueError:
            continue
        if existing_start != starts_at:
            continue

        if addon_names is not None:
            existing_addons = booking.get("addon_names")
            if not isinstance(existing_addons, list):
                continue
            requested = sorted(_normalized_lookup(name) for name in addon_names)
            actual = sorted(_normalized_lookup(str(name)) for name in existing_addons)
            if requested != actual:
                continue
            requested_quantities = {
                _normalized_lookup(name): quantity
                for name, quantity in (addon_quantities or {}).items()
            }
            actual_quantities = _booking_addon_quantities(booking)
            if any(
                actual_quantities.get(name, 1) != requested_quantities.get(name, 1)
                for name in requested
            ):
                continue

            existing_price_source = booking.get("price_source")
            if price_override_amount is None:
                if existing_price_source == "manual_override":
                    continue
            elif (
                existing_price_source != "manual_override"
                or _optional_decimal(booking.get("price_amount"))
                != Decimal(price_override_amount)
            ):
                continue

            existing_duration_source = booking.get("duration_source")
            if duration_override_minutes is None:
                if existing_duration_source == "manual_override":
                    continue
            elif (
                existing_duration_source != "manual_override"
                or booking.get("duration_minutes") != duration_override_minutes
            ):
                continue
        matches.append(booking)
    if len(matches) > 1:
        raise ValueError("ambiguous existing booking")
    return matches[0] if matches else None


def _create_booking(
    values: dict[str, Any],
    *,
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    client_lookup = _call_backend(
        action="find_client",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="GET",
        path="/api/v1/scheduling/clients/exact",
        params={"public_name": values["client_public_name"]},
        json_body=None,
    )
    if not client_lookup.get("ok"):
        return client_lookup
    client_result = client_lookup.get("result")
    if not isinstance(client_result, dict) or not isinstance(client_result.get("found"), bool):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )
    if not client_result["found"]:
        return _error(
            "client_not_found",
            "The client was not found. Confirm and create the client first.",
        )

    day_response = _call_backend(
        action="day_view",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="GET",
        path="/api/v1/scheduling/day",
        params={"day": values["day"]},
        json_body=None,
    )
    if not day_response.get("ok"):
        return day_response

    try:
        day_result = day_response["result"]
        timezone_name = day_result["timezone"]
        if not isinstance(timezone_name, str):
            raise ValueError
        requested_start = _local_datetime(
            values["day"],
            values["start_time"],
            timezone_name,
        )
        existing = _matching_existing_booking(
            day_result,
            client_public_name=values["client_public_name"],
            service_name=values["service_name"],
            starts_at=requested_start,
            addon_names=values["addon_names"],
            addon_quantities=values["addon_quantities"],
            price_override_amount=values["price_override_amount"],
            duration_override_minutes=values["duration_override_minutes"],
        )
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    if existing is not None:
        return {
            "ok": True,
            "action": "create_booking",
            "result": {"booking": existing, "created": False},
        }

    body = {
        "client_public_name": values["client_public_name"],
        "service_name": values["service_name"],
        "addon_names": values["addon_names"],
        "starts_at": requested_start.isoformat(),
        "price_override_amount": values["price_override_amount"],
        "duration_override_minutes": values["duration_override_minutes"],
    }
    if values["addon_quantities"]:
        body["addon_quantities"] = values["addon_quantities"]

    return _call_backend(
        action="create_booking",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="POST",
        path="/api/v1/scheduling/bookings",
        params=None,
        json_body=body,
    )


def _local_datetime(day: str, start_time: str, timezone_name: str) -> datetime:
    return datetime.combine(
        date.fromisoformat(day),
        wall_time.fromisoformat(start_time),
        tzinfo=ZoneInfo(timezone_name),
    )


def _booking_mutation(
    action: str,
    values: dict[str, Any],
    *,
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    day_response = _call_backend(
        action="day_view",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="GET",
        path="/api/v1/scheduling/day",
        params={"day": values["day"]},
        json_body=None,
    )
    if not day_response.get("ok"):
        return day_response

    try:
        result = day_response["result"]
        timezone_name = result["timezone"]
        requested = _local_datetime(
            values["day"],
            values["start_time"],
            timezone_name,
        )
        matches = [
            booking
            for booking in result["bookings"]
            if booking.get("client_public_name") == values["client_public_name"]
            and booking.get("service_name") == values["service_name"]
            and _parse_backend_datetime(booking.get("starts_at")) == requested
        ]
        if len(matches) != 1:
            code = "booking_not_found" if not matches else "booking_ambiguous"
            return _error(code, "The booking could not be resolved uniquely.")

        body = {
            "client_public_name": values["client_public_name"],
            "service_name": values["service_name"],
            "starts_at": requested.isoformat(),
        }
        path = "/api/v1/scheduling/bookings/cancel"

        if action == "reschedule_booking":
            new_start = _local_datetime(
                values["new_day"],
                values["new_start_time"],
                timezone_name,
            )
            body["new_starts_at"] = new_start.isoformat()
            path = "/api/v1/scheduling/bookings/reschedule"
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    return _call_backend(
        action=action,
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="PUT",
        path=path,
        params=None,
        json_body=body,
    )
