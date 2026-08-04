from __future__ import annotations

from datetime import date, time
from pathlib import Path
from types import SimpleNamespace

from app.schemas.scheduling import AvailabilitySummary
from app.schemas.web_schedule import WebScheduleRangeQuery
from app.services.web_schedule import get_web_schedule

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
WEB = APP / "web_static"


def test_schedule_range_is_limited_to_existing_availability_contract():
    query = WebScheduleRangeQuery(
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
    )
    assert query.max_days == 31


def test_web_schedule_reads_existing_day_view(monkeypatch):
    calls: list[date] = []

    def fake_day_view(_session, _identity, day):
        calls.append(day)
        return SimpleNamespace(
            day=day,
            timezone="Europe/Moscow",
            weekday_iso=day.isoweekday(),
            availability_known=True,
            availability=[
                AvailabilitySummary(
                    start_time=time(10, 0),
                    end_time=time(20, 0),
                    is_available=True,
                    note=None,
                )
            ],
            bookings=[object()],
        )

    monkeypatch.setattr("app.services.web_schedule.get_day_view", fake_day_view)
    result = get_web_schedule(
        object(),
        object(),
        WebScheduleRangeQuery(
            date_from=date(2026, 8, 3),
            date_to=date(2026, 8, 4),
        ),
    )

    assert calls == [date(2026, 8, 3), date(2026, 8, 4)]
    assert result.timezone == "Europe/Moscow"
    assert [item.booking_count for item in result.days] == [1, 1]


def test_web_schedule_reuses_existing_preview_and_replace_services():
    source = (APP / "api" / "web_schedule.py").read_text(encoding="utf-8")

    assert "preview_availability(session, identity, body)" in source
    assert "replace_availability(session, identity, body)" in source
    assert "validate_web_boundary(request)" in source
    assert 'prefix="/web/api/schedule"' in source


def test_profile_ui_explains_client_visible_hours_and_day_states():
    source = (WEB / "web-working-schedule.js").read_text(encoding="utf-8")

    assert "Именно в эти часы клиентки видят свободное время для записи" in source
    assert "длительности процедуры" in source
    assert "времени на подготовку и уборку" in source
    assert "уже созданных записей" in source
    assert "Рабочий день" in source
    assert "Выходной" in source
    assert "Не задано" in source
    assert 'api("/web/api/schedule/preview"' in source
    assert 'api("/web/api/schedule"' in source
    assert "Сначала разберитесь с записями" in source


def test_schedule_is_loaded_after_public_profile_and_is_mobile_contained():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "web-working-schedule.css").read_text(encoding="utf-8")

    assert index.index("web-public-profile-visible.js") < index.index("web-working-schedule.js")
    assert "web-working-schedule.css" in index
    assert "minmax(0, 1fr)" in css
    assert "width: 100%" in css


def test_no_parallel_schedule_model_or_schedule_migration_is_added():
    models = (APP / "models.py").read_text(encoding="utf-8")
    migrations = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend" / "alembic" / "versions").glob("*.py")
    )

    assert models.count('class AvailabilityInterval(') == 1
    assert "WeeklySchedule" not in models
    assert "weekly_schedule" not in migrations
    assert "default_week_schedule" not in migrations
