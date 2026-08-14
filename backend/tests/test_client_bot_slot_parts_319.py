from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.client_bot_slot_parts import split_slot_day_parts


def _starts(start: datetime, end: datetime, step_minutes: int = 15) -> list[str]:
    values: list[str] = []
    current = start
    while current < end:
        values.append(current.isoformat())
        current += timedelta(minutes=step_minutes)
    return values


def test_319_full_day_keeps_slots_after_1545_and_matches_engine_count():
    day = date(2026, 8, 20)
    start = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 20, 23, 0, tzinfo=timezone.utc)
    starts = _starts(start, end)

    parts = split_slot_day_parts(
        starts,
        selected_day=day,
        window_start=start,
        window_end=end,
        step_minutes=15,
    )

    assert [part.title for part in parts] == [
        "Утро (10:00–13:00)",
        "День (13:00–17:00)",
        "Вечер (17:00–23:00)",
    ]
    flattened = [value for part in parts for value in part.starts_at]
    assert flattened == starts
    assert any(datetime.fromisoformat(value).strftime("%H:%M") > "15:45" for value in flattened)


def test_319_boundaries_follow_actual_window_and_hide_empty_parts():
    day = date(2026, 8, 20)
    start = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    starts = [
        datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc).isoformat(),
        datetime(2026, 8, 20, 14, 45, tzinfo=timezone.utc).isoformat(),
    ]

    parts = split_slot_day_parts(
        starts,
        selected_day=day,
        window_start=start,
        window_end=end,
        step_minutes=15,
    )

    assert parts[0].title.startswith("Утро (12:00–")
    assert parts[-1].title.endswith("–15:00)")
    assert sum(len(part.starts_at) for part in parts) == len(starts)
    assert all(part.starts_at for part in parts)
