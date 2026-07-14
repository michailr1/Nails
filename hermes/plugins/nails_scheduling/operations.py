from __future__ import annotations

import hashlib
from datetime import date, datetime
from datetime import time as wall_time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .presenters import _normalized_lookup, _parse_backend_datetime
from .transport import _call_backend, _error


def _idempotency_key(
    telegram_user_id: str,
    client_public_name: str,
    service_name: str,
    starts_at: str,
) -> str:
    canonical = "\x1f".join(
        (
            telegram_user_id,
            _normalized_lookup(client_public_name),
            _normalized_lookup(service_name),
            starts_at,
        )
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"nails-scheduling-v1-{digest}"


def _matching_existing_booking(
    day_result: dict[str, Any],
    *,
    client_public_name: str,
    service_name: str,
    starts_at: datetime,
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
        if existing_start == starts_at:
            matches.append(booking)
    if len(matches) > 1:
        raise ValueError("ambiguous existing booking")
    return matches[0] if matches else None


def _create_client(
    values: dict[str, Any],
    *,
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    lookup = _call_backend(
        action="find_client",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="GET",
        path="/api/v1/scheduling/clients/exact",
        params={"public_name": values["client_public_name"]},
        json_body=None,
    )
    if not lookup.get("ok"):
        return lookup
    result = lookup.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("found"), bool):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )
    if result["found"]:
        client = result.get("client")
        if not isinstance(client, dict):
            return _error(
                "invalid_backend_response",
                "Scheduling service returned an invalid response.",
            )
        return {
            "ok": True,
            "action": "create_client",
            "result": {
                "client": client,
                "created": False,
                "contact_added": False,
            },
        }
    return _call_backend(
        action="create_client",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="POST",
        path="/api/v1/scheduling/clients",
        params=None,
        json_body={
            "public_name": values["client_public_name"],
            "phone": values["phone"],
        },
    )


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

    slots_response = _call_backend(
        action="free_slots",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="GET",
        path="/api/v1/scheduling/slots",
        params={"day": values["day"], "service_name": values["service_name"]},
        json_body=None,
    )
    if not slots_response.get("ok"):
        return slots_response
    slots_result = slots_response.get("result")
    if not isinstance(slots_result, dict):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    try:
        timezone_name = slots_result["timezone"]
        step_minutes = slots_result["step_minutes"]
        starts_at_values = slots_result["starts_at"]
        availability_known = slots_result["availability_known"]
        is_working = slots_result["is_working"]
        if not isinstance(timezone_name, str) or not isinstance(step_minutes, int):
            raise ValueError
        if step_minutes <= 0 or step_minutes > 1440 or not isinstance(starts_at_values, list):
            raise ValueError
        timezone = ZoneInfo(timezone_name)
        local_time = wall_time.fromisoformat(values["start_time"])
        local_day = date.fromisoformat(values["day"])
        requested_start = datetime.combine(local_day, local_time, tzinfo=timezone)
        if requested_start.minute % step_minutes != 0:
            return _error(
                "slot_not_on_grid",
                "The requested time is not a valid slot start.",
            )
        free_starts = [_parse_backend_datetime(item) for item in starts_at_values]
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )

    if requested_start not in free_starts:
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
            existing = _matching_existing_booking(
                day_response["result"],
                client_public_name=values["client_public_name"],
                service_name=values["service_name"],
                starts_at=requested_start,
            )
        except (KeyError, TypeError, ValueError):
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
        if availability_known is not True:
            return _error(
                "availability_unknown",
                "Availability is not confirmed for this day.",
            )
        if is_working is not True:
            return _error(
                "day_unavailable",
                "The selected day is not available for bookings.",
            )
        return _error(
            "slot_unavailable",
            "The selected slot is no longer available.",
        )

    starts_at = requested_start.isoformat()
    return _call_backend(
        action="create_booking",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="POST",
        path="/api/v1/scheduling/bookings",
        params=None,
        json_body={
            "client_public_name": values["client_public_name"],
            "service_name": values["service_name"],
            "starts_at": starts_at,
            "idempotency_key": _idempotency_key(
                telegram_user_id,
                values["client_public_name"],
                values["service_name"],
                starts_at,
            ),
        },
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
            slots = _call_backend(
                action="free_slots",
                telegram_user_id=telegram_user_id,
                api_key=api_key,
                method="GET",
                path="/api/v1/scheduling/slots",
                params={
                    "day": values["new_day"],
                    "service_name": values["service_name"],
                },
                json_body=None,
            )
            if not slots.get("ok"):
                return slots
            free = [
                _parse_backend_datetime(item)
                for item in slots["result"]["starts_at"]
            ]
            if new_start not in free:
                return _error(
                    "slot_unavailable",
                    "The selected slot is no longer available.",
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
