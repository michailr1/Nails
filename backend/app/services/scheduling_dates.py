from __future__ import annotations

from datetime import datetime, timedelta

from app.schemas.scheduling import DateResolveRequest, DateResolveResponse
from app.services.scheduling_common import app_timezone


def _local_today():
    return datetime.now(app_timezone()).date()


def resolve_date(body: DateResolveRequest) -> DateResolveResponse:
    timezone = app_timezone()
    today = _local_today()

    if body.kind == "absolute":
        resolved = body.day
    elif body.kind == "relative_days":
        resolved = today + timedelta(days=body.offset_days or 0)
    else:
        weekday_iso = body.weekday_iso
        if weekday_iso is None:
            raise AssertionError("validated weekday_iso is required")
        if body.occurrence == "nearest_future":
            delta = (weekday_iso - today.isoweekday()) % 7
            if delta == 0:
                delta = 7
            resolved = today + timedelta(days=delta)
        else:
            monday = today - timedelta(days=today.isoweekday() - 1)
            week_offset = 0 if body.occurrence == "current_week" else 1
            resolved = monday + timedelta(days=7 * week_offset + weekday_iso - 1)

    if resolved is None:
        raise AssertionError("validated date resolution produced no date")

    return DateResolveResponse(
        timezone=str(timezone),
        today=today,
        today_weekday_iso=today.isoweekday(),
        day=resolved,
        weekday_iso=resolved.isoweekday(),
        is_past=resolved < today,
        kind=body.kind,
        occurrence=body.occurrence,
    )
