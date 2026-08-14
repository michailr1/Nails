from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class SlotDayPart:
    key: str
    title: str
    starts_at: tuple[Any, ...]


_PARTS = (
    ("morning", "Утро", 3),
    ("day", "День", 4),
    ("evening", "Вечер", 6),
)


def _aware_datetime(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("slot day-part datetime must include timezone")
    return parsed


def _round_to_step(value: datetime, *, origin: datetime, step_minutes: int) -> datetime:
    elapsed_minutes = (value - origin).total_seconds() / 60
    steps = round(elapsed_minutes / step_minutes)
    return origin + timedelta(minutes=steps * step_minutes)


def split_slot_day_parts(
    starts_at: list[Any],
    *,
    selected_day: date,
    window_start: Any,
    window_end: Any,
    step_minutes: int,
) -> list[SlotDayPart]:
    """Split available starts without dropping any of them.

    Boundaries are relative to the actual working window returned by the scheduling
    engine. The 3:4:6 weights preserve the product's intended morning/day/evening
    proportions for a 10:00–23:00 window without hard-coding clock hours.
    """
    if step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    start = _aware_datetime(window_start)
    end = _aware_datetime(window_end)
    if end <= start or start.date() != selected_day or end.date() != selected_day:
        raise ValueError("working window must be inside selected day")

    values = [
        (value, _aware_datetime(value))
        for value in starts_at
        if _aware_datetime(value).date() == selected_day
    ]
    span = end - start
    total_weight = sum(weight for _, _, weight in _PARTS)
    first_boundary = _round_to_step(
        start + span * (_PARTS[0][2] / total_weight),
        origin=start,
        step_minutes=step_minutes,
    )
    second_boundary = _round_to_step(
        start + span * ((_PARTS[0][2] + _PARTS[1][2]) / total_weight),
        origin=start,
        step_minutes=step_minutes,
    )
    first_boundary = min(max(first_boundary, start), end)
    second_boundary = min(max(second_boundary, first_boundary), end)
    boundaries = (start, first_boundary, second_boundary, end)

    result: list[SlotDayPart] = []
    assigned = 0
    for index, (key, title, _weight) in enumerate(_PARTS):
        lower = boundaries[index]
        upper = boundaries[index + 1]
        if upper <= lower:
            continue
        part_values = tuple(
            raw
            for raw, parsed in values
            if parsed >= lower and (parsed < upper or (index == 2 and parsed <= upper))
        )
        if not part_values:
            continue
        assigned += len(part_values)
        result.append(
            SlotDayPart(
                key=key,
                title=f"{title} ({lower:%H:%M}–{upper:%H:%M})",
                starts_at=part_values,
            )
        )

    if assigned != len(values):
        raise ValueError("slot day-part split lost available starts")
    return result
