from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"


def test_stability_assets_load_last():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    assert index.index("/web/web-shell-ui.css") < index.index("/web/web-mobile-stability.css")
    assert index.index("/web/web-shell-navigation.js") < index.index("/web/web-view-stability.js")


def test_mobile_shell_cannot_overflow_document():
    css = (WEB / "web-mobile-stability.css").read_text(encoding="utf-8")
    assert "overflow-x: clip" in css
    assert "#app" in css
    assert ".app-shell" in css
    assert ".main" in css
    assert "#page-content" in css
    assert "left: 12px" in css
    assert "right: 12px" in css
    assert "width: auto" in css
    assert "bottom: calc(18px + env(safe-area-inset-bottom))" in css


def test_stale_calendar_and_statistics_render_recover_active_view():
    js = (WEB / "web-view-stability.js").read_text(encoding="utf-8")
    assert "const stableRenderCalendar = renderCalendar" in js
    assert 'requestedView === "calendar" && state.view !== "calendar"' in js
    assert "const stableRenderStatistics = renderStatistics" in js
    assert 'requestedView === "statistics" && state.view !== "statistics"' in js
    assert js.count("return renderApp()") == 2


def test_general_link_is_named_as_telegram_invitation():
    js = (WEB / "web-view-stability.js").read_text(encoding="utf-8")
    assert "Пригласить клиентку в Telegram" in js
    assert "Приглашение клиентки в Telegram" in js
