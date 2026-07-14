from __future__ import annotations

from datetime import datetime
from typing import Any


def _service_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid service")
    fields = (
        "public_name", "public_description", "price_amount", "currency",
        "duration_minutes", "buffer_before_minutes", "buffer_after_minutes", "is_active",
    )
    if not set(fields).issubset(value):
        raise ValueError("invalid service")
    return {key: value[key] for key in fields}


def _client_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not {"public_name", "phone"}.issubset(value):
        raise ValueError("invalid client")
    return {"public_name": value["public_name"], "phone": value["phone"]}


def _availability_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid availability")
    fields = ("start_time", "end_time", "is_available", "note")
    if not set(fields).issubset(value):
        raise ValueError("invalid availability")
    return {key: value[key] for key in fields}


def _availability_day_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("availability"), list):
        raise ValueError("invalid availability day")
    return {
        "day": value["day"],
        "weekday_iso": value["weekday_iso"],
        "availability_known": value["availability_known"],
        "availability": [_availability_summary(item) for item in value["availability"]],
        "changed": value["changed"],
    }


def _booking_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid booking")
    fields = (
        "client_public_name", "service_name", "starts_at", "ends_at",
        "reserved_starts_at", "reserved_ends_at", "status", "price_amount",
        "currency", "duration_minutes", "buffer_before_minutes", "buffer_after_minutes",
    )
    if not set(fields).issubset(value):
        raise ValueError("invalid booking")
    return {key: value[key] for key in fields}


def _sanitize_success(action: str, result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("invalid result")
    if action == "resolve_date":
        fields = ("timezone", "today", "today_weekday_iso", "day", "weekday_iso", "is_past", "kind", "occurrence")
        if not set(fields).issubset(result):
            raise ValueError("invalid resolved date")
        return {key: result[key] for key in fields}
    if action == "list_services":
        services = result.get("services")
        if not isinstance(services, list):
            raise ValueError("invalid services")
        return {"services": [_service_summary(item) for item in services]}
    if action == "find_service":
        service = result.get("service")
        return {"found": result["found"], "service": None if service is None else _service_summary(service)}
    if action == "create_service":
        return {"service": _service_summary(result["service"]), "created": result["created"]}
    if action == "update_service":
        changed_fields = result.get("changed_fields")
        if not isinstance(changed_fields, list) or not all(isinstance(field, str) for field in changed_fields):
            raise ValueError("invalid changed fields")
        return {"service": _service_summary(result["service"]), "changed": result["changed"], "changed_fields": changed_fields}
    if action == "day_view":
        availability = result.get("availability")
        bookings = result.get("bookings")
        if not isinstance(availability, list) or not isinstance(bookings, list):
            raise ValueError("invalid day view")
        return {
            "day": result["day"], "timezone": result["timezone"], "weekday_iso": result["weekday_iso"],
            "availability_known": result["availability_known"],
            "availability": [_availability_summary(item) for item in availability],
            "bookings": [_booking_summary(item) for item in bookings],
        }
    if action == "free_slots":
        starts_at = result.get("starts_at")
        if not isinstance(starts_at, list):
            raise ValueError("invalid slots")
        return {
            "day": result["day"], "timezone": result["timezone"], "weekday_iso": result["weekday_iso"],
            "availability_known": result["availability_known"], "is_working": result["is_working"],
            "step_minutes": result["step_minutes"], "service": _service_summary(result["service"]),
            "starts_at": starts_at,
        }
    if action == "find_client":
        client = result.get("client")
        return {"found": result["found"], "client": None if client is None else _client_summary(client)}
    if action == "find_client_candidates":
        candidates = result.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("invalid client candidates")
        return {"candidates": [_client_summary(item) for item in candidates]}
    if action == "create_client":
        return {"client": _client_summary(result["client"]), "created": result["created"], "contact_added": result["contact_added"]}
    if action == "update_availability":
        days = result.get("days")
        if not isinstance(days, list):
            raise ValueError("invalid availability update")
        return {"days": [_availability_day_result(item) for item in days]}
    if action == "create_booking":
        return {"booking": _booking_summary(result["booking"]), "created": result["created"]}
    if action in {"reschedule_booking", "cancel_booking"}:
        return {"booking": _booking_summary(result["booking"]), "changed": result["changed"]}
    raise ValueError("unsupported result action")


def _normalized_lookup(value: str) -> str:
    return " ".join(value.split()).casefold()


def _parse_backend_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("invalid datetime")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone is required")
    return parsed
