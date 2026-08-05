from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.services.scheduling_common import is_representable_local_datetime


def test_spring_gap_wall_times_are_not_representable():
    assert not is_representable_local_datetime(
        datetime(2026, 3, 8, 2, 15, tzinfo=ZoneInfo("America/New_York"))
    )
    assert not is_representable_local_datetime(
        datetime(2026, 3, 29, 2, 15, tzinfo=ZoneInfo("Europe/Berlin"))
    )
    assert is_representable_local_datetime(
        datetime(2026, 3, 8, 3, 15, tzinfo=ZoneInfo("America/New_York"))
    )
    assert datetime(2026, 8, 6, 2, 30, tzinfo=UTC).astimezone(
        ZoneInfo("America/New_York")
    ).strftime("%d.%m в %H:%M") == "05.08 в 22:30"
