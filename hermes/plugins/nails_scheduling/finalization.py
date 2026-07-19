from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfoNotFoundError

from .operations import _local_datetime, _matching_existing_booking
from .transport import _call_backend, _error
from .validation import (
    ToolInputError,
    _confirmed,
    _day,
    _keys,
    _price,
    _text,
    _time,
)


def validate_finalize_booking_args(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "action",
        "client_public_name",
        "service_name",
        "day",
        "start_time",
        "outcome",
        "price_amount",
        "confirmed",
    }
    required = allowed - {"price_amount"}
    _keys(args, allowed, required)
    _confirmed(args)

    outcome = args.get("outcome")
    if outcome not in {"completed", "no_show"}:
        raise ToolInputError("booking outcome is invalid")
    price_amount = None
    if args.get("price_amount") is not None:
        price_amount = _price(args.get("price_amount"))
    if outcome == "no_show" and price_amount is not None:
        raise ToolInputError("no_show cannot contain price_amount")

    return {
        "client_public_name": _text(
            args.get("client_public_name"),
            "client_public_name",
            160,
        ),
        "service_name": _text(args.get("service_name"), "service_name", 160),
        "day": _day(args.get("day")),
        "start_time": _time(args.get("start_time")),
        "outcome": outcome,
        "price_amount": price_amount,
    }


def _day_view(
    day: str,
    *,
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    return _call_backend(
        action="day_view",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="GET",
        path="/api/v1/scheduling/day",
        params={"day": day},
        json_body=None,
    )


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid booking price") from exc


def _same_finalization(
    write_booking: dict[str, Any],
    read_booking: dict[str, Any],
) -> bool:
    scalar_fields = (
        "status",
        "price_source",
        "price_confirmed",
        "currency",
        "duration_minutes",
        "duration_source",
    )
    if any(write_booking.get(field) != read_booking.get(field) for field in scalar_fields):
        return False
    return _decimal(write_booking.get("price_amount")) == _decimal(
        read_booking.get("price_amount")
    )


def finalize_booking(
    values: dict[str, Any],
    *,
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    source_response = _day_view(
        values["day"],
        telegram_user_id=telegram_user_id,
        api_key=api_key,
    )
    if not source_response.get("ok"):
        return source_response

    try:
        source_result = source_response["result"]
        timezone_name = source_result["timezone"]
        starts_at = _local_datetime(
            values["day"],
            values["start_time"],
            timezone_name,
        )
        source_booking = _matching_existing_booking(
            source_result,
            client_public_name=values["client_public_name"],
            service_name=values["service_name"],
            starts_at=starts_at,
        )
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )
    if source_booking is None:
        return _error("booking_not_found", "The booking could not be resolved uniquely.")

    response = _call_backend(
        action="finalize_booking",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="PUT",
        path="/api/v1/scheduling/bookings/finalize",
        params=None,
        json_body={
            "client_public_name": values["client_public_name"],
            "service_name": values["service_name"],
            "starts_at": starts_at.isoformat(),
            "outcome": values["outcome"],
            "price_amount": values["price_amount"],
        },
    )
    if not response.get("ok"):
        return response

    result = response.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("changed"), bool):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )
    write_booking = result.get("booking")
    if not isinstance(write_booking, dict):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    readback_response = _day_view(
        values["day"],
        telegram_user_id=telegram_user_id,
        api_key=api_key,
    )
    if not readback_response.get("ok"):
        return readback_response
    try:
        read_booking = _matching_existing_booking(
            readback_response["result"],
            client_public_name=values["client_public_name"],
            service_name=values["service_name"],
            starts_at=starts_at,
        )
    except (KeyError, TypeError, ValueError):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )
    if read_booking is None or not _same_finalization(write_booking, read_booking):
        return _error(
            "mutation_verification_failed",
            "The booking change could not be verified.",
        )

    return {
        "ok": True,
        "action": "finalize_booking",
        "result": {
            "booking": write_booking,
            "changed": result["changed"],
            "verified": True,
        },
    }
