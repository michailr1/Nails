from __future__ import annotations

from datetime import date, datetime
from datetime import time as wall_time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .presenters import _parse_backend_datetime
from .transport import _call_backend, _error


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
        requested = _local_datetime(values["day"], values["start_time"], timezone_name)
        matches = [
            booking
            for booking in result["bookings"]
            if booking.get("client_public_name") == values["client_public_name"]
            and booking.get("service_name") == values["service_name"]
            and _parse_backend_datetime(booking.get("starts_at")) == requested
        ]
        if len(matches) != 1:
            return _error(
                "booking_not_found" if not matches else "booking_ambiguous",
                "The booking could not be resolved uniquely.",
            )
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
                params={"day": values["new_day"], "service_name": values["service_name"]},
                json_body=None,
            )
            if not slots.get("ok"):
                return slots
            free = [_parse_backend_datetime(item) for item in slots["result"]["starts_at"]]
            if new_start not in free:
                return _error("slot_unavailable", "The selected slot is no longer available.")
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
