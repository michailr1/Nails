from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"


def test_321_calendar_day_controls_use_existing_preview_before_replace():
    source = (WEB / "web-calendar-availability.js").read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert "Не работаю в этот день" in source
    assert "Другое время в этот день" in source
    assert 'api("/web/api/schedule/preview"' in source
    assert 'api("/web/api/schedule"' in source
    assert source.index('api("/web/api/schedule/preview"') < source.index('api("/web/api/schedule"')
    assert "can_apply" in source
    assert "conflicts" in source
    assert "client_public_name" in source
    assert "service_name" in source
    assert "web-calendar-availability.js" in index
    assert "web-calendar-availability.css" in index


def test_321_day_off_is_visible_in_week_and_month_and_days_open_from_calendar():
    source = (WEB / "web-calendar-availability.js").read_text(encoding="utf-8")

    assert "calendarDayStatus" in source
    assert 'class="calendar-day-off"' in source
    assert "groupedCalendar" in source
    assert "monthPanel" in source
    assert "data-open-date" in source
    assert "Выходной" in source


def test_321_keeps_single_day_mental_model_and_does_not_restore_14_day_editor():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    source = (WEB / "web-calendar-availability.js").read_text(encoding="utf-8")

    assert not (WEB / "web-working-schedule.js").exists()
    assert not (WEB / "web-working-schedule.css").exists()
    assert "web-working-schedule" not in index
    assert "date_from" not in source
    assert "date_to" not in source
    assert "отпуск" not in source.lower()


def test_321_account_button_is_in_topbar_flow_not_fixed_or_sticky():
    settings = (WEB / "web-master-settings.js").read_text(encoding="utf-8")
    css = (WEB / "web-master-settings.css").read_text(encoding="utf-8")

    host_block = css.split(".master-account-host {", 1)[1].split("}", 1)[0]
    assert "position: fixed" not in host_block
    assert "position: sticky" not in host_block
    assert "position: relative" in host_block
    assert "margin-left: auto" in host_block

    assert 'document.querySelector(".sidebar-bottom")?.remove()' in settings
    assert 'document.querySelector(".mobile-logout")?.remove()' in settings
    assert '.topbar-side > .logout-button' in settings
