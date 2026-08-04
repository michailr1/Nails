from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.schemas.web_schedule import WebScheduleDay, WebScheduleRangeQuery, WebScheduleResponse
from app.services.scheduling_queries import get_day_view


def get_web_schedule(
    session: Session,
    identity: RequestIdentity,
    query: WebScheduleRangeQuery,
) -> WebScheduleResponse:
    days: list[WebScheduleDay] = []
    timezone: str | None = None
    current = query.date_from
    while current <= query.date_to:
        view = get_day_view(session, identity, current)
        timezone = timezone or view.timezone
        days.append(
            WebScheduleDay(
                day=view.day,
                weekday_iso=view.weekday_iso,
                availability_known=view.availability_known,
                availability=view.availability,
                booking_count=len(view.bookings),
            )
        )
        current += timedelta(days=1)
    return WebScheduleResponse(
        timezone=timezone or "UTC",
        date_from=query.date_from,
        date_to=query.date_to,
        days=days,
    )
