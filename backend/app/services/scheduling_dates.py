from __future__ import annotations

from datetime import date, datetime, timedelta

from app.schemas.scheduling import DateResolveRequest, DateResolveResponse
from app.services.scheduling_common import SchedulingDomainError, app_timezone


def _local_today() -> date:
    return datetime.now(app_timezone()).date()


def _date_in_year(year: int, month: int, day_of_month: int) -> date:
    try:
        return date(year, month, day_of_month)
    except ValueError as exc:
        raise SchedulingDomainError(
            "date_not_valid_in_year",
            status_code=422,
            details={"year": year, "month": month, "day_of_month": day_of_month},
        ) from exc


def _nearest_future_month_day(today: date, month: int, day_of_month: int) -> date:
    for year in range(today.year, today.year + 9):
        try:
            candidate = date(year, month, day_of_month)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    raise SchedulingDomainError("date_resolution_failed", status_code=422)


def resolve_date(body: DateResolveRequest) -> DateResolveResponse:
    timezone = app_timezone()
    today = _local_today()

    if body.kind == "absolute":
        resolved = body.day
    elif body.kind == "month_day":
        if body.month is None or body.day_of_month is None:
            raise AssertionError("validated month and day are required")
        if body.occurrence == "nearest_future":
            resolved = _nearest_future_month_day(today, body.month, body.day_of_month)
        elif body.occurrence == "current_year":
            resolved = _date_in_year(today.year, body.month, body.day_of_month)
        else:
            resolved = _date_in_year(today.year + 1, body.month, body.day_of_month)
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
