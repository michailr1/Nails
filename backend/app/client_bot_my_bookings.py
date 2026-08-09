from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_VISIBLE_STATUSES = {"pending", "approved"}
_STATUS_LABELS = {
    "pending": "⏳ ждёт подтверждения",
    "approved": "✅ подтверждена",
}


def _master_timezone(master: dict[str, Any]) -> ZoneInfo:
    raw = str(master.get("timezone") or "Europe/Moscow").strip()
    try:
        return ZoneInfo(raw)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def _starts_at(request: dict[str, Any]) -> datetime:
    value = str(request.get("starts_at") or "")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("booking request starts_at must include timezone")
    return parsed


def upcoming_booking_requests(
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must include timezone")
    result = [
        request
        for request in payload.get("requests") or []
        if str(request.get("status") or "") in _VISIBLE_STATUSES
        and _starts_at(request).astimezone(UTC) >= current.astimezone(UTC)
    ]
    result.sort(key=lambda request: _starts_at(request).astimezone(UTC))
    return result


def booking_request_text(
    request: dict[str, Any],
    master: dict[str, Any],
) -> str:
    timezone = _master_timezone(master)
    starts_at = _starts_at(request).astimezone(timezone)
    status = str(request.get("status") or "")
    service_name = str(request.get("service_name") or "Процедура").strip()
    lines = [f"{starts_at:%d.%m в %H:%M} — {service_name}"]
    quantities = request.get("addon_quantities") or {}
    for addon_name in request.get("addon_names") or []:
        name = str(addon_name)
        quantity = int(quantities.get(name.casefold(), 1))
        suffix = f" ×{quantity}" if quantity > 1 else ""
        lines.append(f"+ {name}{suffix}")
    lines.append(_STATUS_LABELS[status])
    return "\n".join(lines)
