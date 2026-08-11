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


def test_usual_hours_are_one_setting_under_master_icon():
    source = (WEB / "web-master-settings.js").read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert "data-master-account" in source
    assert "Меню мастера" in source
    assert "Настройки" in source
    assert "Часовой пояс" in source
    assert "Обычные рабочие часы" in source
    assert "Исключение на конкретную дату задаётся в Календаре" in source
    assert 'intervals: [{' in source
    assert 'api("/web/api/schedule/default-work-hours"' in source
    assert "web-master-settings.js" in index
    assert "web-master-settings.css" in index


def test_master_account_menu_finishes_286_by_moving_not_duplicating_controls():
    settings = (WEB / "web-master-settings.js").read_text(encoding="utf-8")
    profile = (WEB / "web-public-profile-visible.js").read_text(encoding="utf-8")
    css = (WEB / "web-master-settings.css").read_text(encoding="utf-8")

    assert 'document.querySelector(".topbar-side")' not in settings
    assert "master-account-host" in settings
    assert "Профиль для клиенток" in settings
    assert "data-open-master-settings" in settings
    assert "data-master-logout" in settings
    assert "confirmMasterLogout" in settings

    # Старые элементы удаляются из фактического shell, а не остаются рядом с меню.
    assert 'document.querySelector(".sidebar-bottom")?.remove()' in settings
    assert 'document.querySelector(".mobile-logout")?.remove()' in settings

    # Профиль больше не монтируется в раздел Клиентки; он открывается из account menu.
    assert "renderPublicProfileOutsideClients() {}" in profile
    assert "page.prepend(panel)" not in profile
    assert "renderMasterPublicProfile" in profile

    # Аватар имеет отдельную угловую геометрию, а mobile dialog ограничен viewport.
    assert ".master-account-host" in css
    assert "position: absolute" in css
    assert "calc(100vw - 20px)" in css
    assert "calc(100dvh - 20px)" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)" in css


def test_legacy_14_day_editor_is_removed_instead_of_duplicated():
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert not (WEB / "web-working-schedule.js").exists()
    assert not (WEB / "web-working-schedule.css").exists()
    assert "web-working-schedule.js" not in index
    assert "web-working-schedule.css" not in index
    assert "WORKING_SCHEDULE_DAYS" not in "\n".join(
        path.read_text(encoding="utf-8") for path in WEB.glob("*.js")
    )


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
