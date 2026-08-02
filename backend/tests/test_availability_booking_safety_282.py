from __future__ import annotations

from datetime import date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.schemas.scheduling import AvailabilityDayReplace, AvailabilityIntervalInput
from app.services.scheduling_availability import _booking_fits_update

DAY = date(2026, 8, 10)
TZ = ZoneInfo("Europe/Moscow")
BOOKING = SimpleNamespace(
    reserved_starts_at=datetime(2026, 8, 10, 12, 0, tzinfo=TZ),
    reserved_ends_at=datetime(2026, 8, 10, 14, 0, tzinfo=TZ),
)


def available(start: time, end: time) -> AvailabilityDayReplace:
    return AvailabilityDayReplace(
        day=DAY,
        state="available",
        intervals=[AvailabilityIntervalInput(start_time=start, end_time=end)],
    )


def test_booking_fits_when_new_interval_contains_full_reserved_window(monkeypatch):
    monkeypatch.setattr("app.services.scheduling_availability.app_timezone", lambda: TZ)

    assert _booking_fits_update(BOOKING, available(time(10, 0), time(20, 0)))
    assert _booking_fits_update(BOOKING, available(time(12, 0), time(14, 0)))


def test_narrowing_before_booking_end_is_blocked(monkeypatch):
    monkeypatch.setattr("app.services.scheduling_availability.app_timezone", lambda: TZ)

    assert not _booking_fits_update(BOOKING, available(time(10, 0), time(13, 59)))


def test_narrowing_after_booking_start_is_blocked(monkeypatch):
    monkeypatch.setattr("app.services.scheduling_availability.app_timezone", lambda: TZ)

    assert not _booking_fits_update(BOOKING, available(time(12, 1), time(20, 0)))


def test_split_intervals_must_contain_booking_in_one_interval(monkeypatch):
    monkeypatch.setattr("app.services.scheduling_availability.app_timezone", lambda: TZ)
    update = AvailabilityDayReplace(
        day=DAY,
        state="available",
        intervals=[
            AvailabilityIntervalInput(start_time=time(10, 0), end_time=time(13, 0)),
            AvailabilityIntervalInput(start_time=time(13, 30), end_time=time(20, 0)),
        ],
    )

    assert not _booking_fits_update(BOOKING, update)


def test_unavailable_conflicts_but_unknown_preserves_explicit_booking(monkeypatch):
    monkeypatch.setattr("app.services.scheduling_availability.app_timezone", lambda: TZ)

    unavailable = AvailabilityDayReplace(day=DAY, state="unavailable")
    unknown = AvailabilityDayReplace(day=DAY, state="unknown")

    assert not _booking_fits_update(BOOKING, unavailable)
    assert _booking_fits_update(BOOKING, unknown)
