from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.client_bot_booking_flow import draft_day_part_keyboard
from app.client_bot_slot_parts import split_slot_day_parts

DRAFT_ID = "11111111-1111-4111-8111-111111111111"


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


def test_319_day_part_keyboard_exposes_all_actual_ranges():
    day = date(2026, 8, 20)
    start = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 20, 23, 0, tzinfo=timezone.utc)
    starts = _starts(start, end)
    keyboard = draft_day_part_keyboard(
        DRAFT_ID,
        {
            "starts_at": starts,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "step_minutes": 15,
        },
        selected_day=day,
    )

    buttons = [row[0] for row in keyboard["inline_keyboard"][:-1]]
    assert [button["text"] for button in buttons] == [
        "Утро (10:00–13:00)",
        "День (13:00–17:00)",
        "Вечер (17:00–23:00)",
    ]
    assert [button["callback_data"].rsplit(":", 1)[-1] for button in buttons] == [
        "morning",
        "day",
        "evening",
    ]


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


def test_319_no_client_slot_picker_silently_truncates_to_24():
    app_root = Path(__file__).resolve().parents[1] / "app"
    for relative in ("client_bot.py", "client_bot_booking_flow.py"):
        source = (app_root / relative).read_text(encoding="utf-8")
        assert "starts_at[:24]" not in source
