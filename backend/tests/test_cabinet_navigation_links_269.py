from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"
INDEX = WEB / "index.html"
STYLES = WEB / "styles.css"
SHELL_CSS = WEB / "web-shell-ui.css"
SHELL_JS = WEB / "web-shell-navigation.js"
REACHABILITY = WEB / "web-client-reachability.js"


def test_mobile_hidden_brand_wins_after_non_media_glam_rule():
    index = INDEX.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    shell = SHELL_CSS.read_text(encoding="utf-8")

    assert ".sidebar .brand,\n.center-brand .brand" in styles
    assert "display: inline-flex" in styles
    assert index.index('/web/styles.css') < index.index('/web/web-shell-ui.css')
    assert re.search(
        r"@media\s*\(max-width:\s*760px\)\s*\{[\s\S]*?"
        r"\.app-shell\s+\.sidebar\s+\.brand,\s*"
        r"\.app-shell\s+\.sidebar-bottom\s*\{[^}]*display:\s*none;",
        shell,
    )
    assert "!important" not in shell


def test_mobile_bottom_panel_contains_navigation_only():
    shell = SHELL_CSS.read_text(encoding="utf-8")

    assert ".app-shell .sidebar .brand" in shell
    assert ".app-shell .sidebar-bottom" in shell
    assert ".sidebar > .nav" in shell
    assert "min-height: 48px" in shell


def test_section_route_survives_refresh_and_browser_back():
    index = INDEX.read_text(encoding="utf-8")
    routing = SHELL_JS.read_text(encoding="utf-8")

    assert index.rindex('/web/web-shell-navigation.js') > index.index('/web/app.js')
    for view in ("calendar", "clients", "services", "statistics"):
        assert f'"{view}"' in routing
    assert 'CABINET_ROUTE_PARAM = "section"' in routing
    assert "URLSearchParams" not in routing  # URL.searchParams is the canonical source
    assert ".searchParams.get(CABINET_ROUTE_PARAM)" in routing
    assert "window.history[method]" in routing
    assert 'window.addEventListener("popstate", cabinetRestoreView)' in routing
    assert "state.view = initialCabinetView" in routing


def test_mobile_logout_is_separate_and_requires_confirmation():
    shell = SHELL_CSS.read_text(encoding="utf-8")
    routing = SHELL_JS.read_text(encoding="utf-8")

    assert ".topbar-side > .mobile-logout" in shell
    assert "position: absolute" in shell
    assert "right: 0" in shell
    assert "width: auto" in shell
    assert 'event.target.closest(".logout-button")' in routing
    assert "window.confirm" in routing
    assert "Для повторного входа потребуется подтверждение в Telegram" in routing
    assert "event.stopImmediatePropagation()" in routing


def test_secondary_actions_are_visually_discoverable():
    shell = SHELL_CSS.read_text(encoding="utf-8")

    block = shell.split(".secondary-button {", 1)[1].split("}", 1)[0]
    assert "border: 1px solid var(--border)" in block
    assert "background: color-mix" in block
    assert "box-shadow:" in block


def test_general_and_personal_links_have_distinct_copy():
    source = REACHABILITY.read_text(encoding="utf-8")

    assert "Общая ссылка для записи" in source
    assert "Подходит для любой новой клиентки" in source
    assert "Ссылка для этой клиентки" in source
    assert "Скопировать ссылку" in source
    assert "Кнопка сразу скопирует готовую ссылку" in source
    assert "Пригласить клиенток" not in source
    assert "data-personal-invite" in source
    assert "await copyText(payload.invitation_url, status)" in source
    assert "prompt(" not in source


def test_reachability_is_always_next_to_name_with_section_summary():
    source = REACHABILITY.read_text(encoding="utf-8")
    shell = SHELL_CSS.read_text(encoding="utf-8")

    assert ".client-card-summary-main strong, h3" in source
    assert 'row.className = "client-name-status"' in source
    assert "client-reachability-badge" in source
    assert "renderReachabilitySummary(reachability)" in source
    assert "из ${items.length} на связи" in source
    assert ".client-name-status" in shell
    assert ".client-reachability-summary" in shell
