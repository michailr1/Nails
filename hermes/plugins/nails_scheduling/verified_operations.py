from __future__ import annotations

from datetime import datetime
from typing import Any

from .operations import (
    _booking_mutation,
    _create_booking,
    _local_datetime,
    _matching_existing_booking,
)
from .transport import _call_backend, _error


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


def _verified_create_booking(
    values: dict[str, Any],
    *,
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    response = _create_booking(
        values,
        telegram_user_id=telegram_user_id,
        api_key=api_key,
    )
    if not response.get("ok"):
        return response

    result = response.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("created"), bool):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    day_response = _day_view(
        values["day"],
        telegram_user_id=telegram_user_id,
        api_key=api_key,
    )
    if not day_response.get("ok"):
        return day_response

    try:
        write_booking = result["booking"]
        if not isinstance(write_booking, dict):
            raise ValueError
        starts_at = datetime.fromisoformat(write_booking["starts_at"])
        if starts_at.tzinfo is None or starts_at.utcoffset() is None:
            raise ValueError
        verified_booking = _matching_existing_booking(
            day_response["result"],
            client_public_name=values["client_public_name"],
            service_name=values["service_name"],
            starts_at=starts_at,
            addon_names=values["addon_names"],
            addon_quantities=values["addon_quantities"],
            price_override_amount=values["price_override_amount"],
            duration_override_minutes=values["duration_override_minutes"],
        )
    except (KeyError, TypeError, ValueError):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    if verified_booking is None:
        return _error(
            "mutation_verification_failed",
            "The booking change could not be verified.",
        )

    return {
        "ok": True,
        "action": "create_booking",
        "result": {
            "booking": write_booking,
            "created": result["created"],
            "verified": True,
        },
    }


def _verified_booking_mutation(
    action: str,
    values: dict[str, Any],
    *,
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    response = _booking_mutation(
        action,
        values,
        telegram_user_id=telegram_user_id,
        api_key=api_key,
    )
    if not response.get("ok"):
        return response

    result = response.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("changed"), bool):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    source_response = _day_view(
        values["day"],
        telegram_user_id=telegram_user_id,
        api_key=api_key,
    )
    if not source_response.get("ok"):
        return source_response

    try:
        source_timezone = source_response["result"]["timezone"]
        source_start = _local_datetime(
            values["day"],
            values["start_time"],
            source_timezone,
        )
        source_booking = _matching_existing_booking(
            source_response["result"],
            client_public_name=values["client_public_name"],
            service_name=values["service_name"],
            starts_at=source_start,
        )
    except (KeyError, TypeError, ValueError):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    if action == "cancel_booking":
        if source_booking is not None:
            return _error(
                "mutation_verification_failed",
                "The booking change could not be verified.",
            )
        return {
            "ok": True,
            "action": action,
            "result": {
                "booking": result["booking"],
                "changed": result["changed"],
                "verified": True,
            },
        }

    target_response = source_response
    if values["new_day"] != values["day"]:
        target_response = _day_view(
            values["new_day"],
            telegram_user_id=telegram_user_id,
            api_key=api_key,
        )
        if not target_response.get("ok"):
            return target_response

    try:
        target_timezone = target_response["result"]["timezone"]
        target_start = _local_datetime(
            values["new_day"],
            values["new_start_time"],
            target_timezone,
        )
        target_booking = _matching_existing_booking(
            target_response["result"],
            client_public_name=values["client_public_name"],
            service_name=values["service_name"],
            starts_at=target_start,
        )
    except (KeyError, TypeError, ValueError):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    same_position = (
        values["day"] == values["new_day"]
        and values["start_time"] == values["new_start_time"]
    )
    source_cleared = source_booking is None or same_position
    if target_booking is None or not source_cleared:
        return _error(
            "mutation_verification_failed",
            "The booking change could not be verified.",
        )

    return {
        "ok": True,
        "action": action,
        "result": {
            "booking": target_booking,
            "changed": result["changed"],
            "verified": True,
        },
    }
