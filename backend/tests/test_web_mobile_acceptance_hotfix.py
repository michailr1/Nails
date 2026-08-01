from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).parents[1] / "app" / "web_static"


def test_internal_scheduled_status_is_not_rendered_to_master() -> None:
    source = (STATIC / "web-booking-edit.js").read_text(encoding="utf-8")

    assert 'scheduled: "Запланирована"' not in source
    assert 'statusLabel ? `<span class="badge">' in source
    assert 'booking.status === "scheduled" || booking.status === "completed"' in source


def test_past_scheduled_booking_remains_editable() -> None:
    source = (STATIC / "web-booking-edit.js").read_text(encoding="utf-8")

    assert "Date.now()" not in source
    assert 'booking.status === "scheduled"' in source
    assert "/web/api/bookings/${booking.booking_id}" in source
    assert "/web/api/bookings/cancel" in source


def test_native_time_wheels_are_replaced_with_theme_aware_selects() -> None:
    edit = (STATIC / "web-booking-edit.js").read_text(encoding="utf-8")
    mobile = (STATIC / "web-mobile-acceptance.js").read_text(encoding="utf-8")
    css = (STATIC / "web-booking.css").read_text(encoding="utf-8")

    assert 'type="datetime-local"' not in edit
    assert 'type="time"' not in edit
    assert 'input[name="time"]' in mobile
    assert 'select name="${name}"' in mobile
    assert 'select[name="time"]' in css
    assert "background: var(--surface)" in css
    assert "color: var(--text)" in css
    assert "color-scheme: light" not in css


def test_statistics_period_switch_uses_two_columns_on_mobile() -> None:
    css = (STATIC / "web-statistics.css").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "@media (max-width: 720px)" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "/web/web-statistics.css" in index
    assert "/web/web-mobile-acceptance.js" in index
