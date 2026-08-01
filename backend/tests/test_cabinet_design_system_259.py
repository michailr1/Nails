from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"
INDEX = WEB / "index.html"
STYLES = WEB / "styles.css"
CLIENTS = WEB / "web-clients.css"
MOBILE_LAYOUT = WEB / "web-mobile-acceptance.js"

COLOR_LITERAL = re.compile(
    r"(?<![\w-])(?:#[0-9a-fA-F]{3,8}\b|rgba?\s*\()"
)
BASE_LAYOUT_SELECTORS = {
    ".app-shell",
    ".main",
    ".nav",
    ".sidebar",
    ".topbar",
}
SELECTOR_BLOCK = re.compile(r"([^{}]+)\{")
NAV_VIEW = re.compile(
    r'(?:data-view=["\']|dataset\.view\s*=\s*["\'])([a-z-]+)'
)


def _linked_css_files() -> list[Path]:
    source = INDEX.read_text(encoding="utf-8")
    hrefs = re.findall(r'href="/web/([^\"]+\.css)"', source)
    return [WEB / href for href in hrefs]


def _linked_js_files() -> list[Path]:
    source = INDEX.read_text(encoding="utf-8")
    srcs = re.findall(r'src="/web/([^\"]+\.js)"', source)
    return [WEB / src for src in srcs]


def _defined_selectors(source: str) -> set[str]:
    selectors: set[str] = set()
    for match in SELECTOR_BLOCK.finditer(source):
        prelude = match.group(1).strip()
        if prelude.startswith("@"):
            continue
        for selector in prelude.split(","):
            selectors.add(selector.strip())
    return selectors


def _actual_navigation_views() -> set[str]:
    views: set[str] = set()
    for path in _linked_js_files():
        views.update(NAV_VIEW.findall(path.read_text(encoding="utf-8")))
    return views


def test_feature_css_uses_design_tokens_instead_of_color_literals():
    violations: list[str] = []
    for path in _linked_css_files():
        if path.name == "styles.css":
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if COLOR_LITERAL.search(line):
                violations.append(f"{path.name}:{line_number}: {line.strip()}")

    assert not violations, "feature CSS contains literal colors:\n" + "\n".join(violations)


def test_base_layout_selectors_are_defined_only_in_styles_css():
    violations: list[str] = []
    for path in _linked_css_files():
        if path.name == "styles.css":
            continue
        selectors = _defined_selectors(path.read_text(encoding="utf-8"))
        for base_selector in sorted(BASE_LAYOUT_SELECTORS & selectors):
            violations.append(f"{path.name}: {base_selector}")

    assert not violations, "feature CSS redefines base layout:\n" + "\n".join(
        violations
    )


def test_cabinet_no_longer_loads_patch_named_css_files():
    patch_markers = ("-fix", "-acceptance", "-grammar", "-copy-fix")
    loaded = [
        path.name
        for path in _linked_css_files()
        if any(marker in path.stem for marker in patch_markers)
    ]
    assert not loaded, f"patch CSS is still loaded: {loaded}"


def test_mobile_navigation_columns_follow_actual_tabs_without_fixed_count():
    styles = STYLES.read_text(encoding="utf-8")
    views = _actual_navigation_views()

    assert len(views) >= 4, f"expected current cabinet tabs, found: {sorted(views)}"
    assert re.search(
        r"\.nav\s*\{[^}]*grid-auto-flow:\s*column;"
        r"[^}]*grid-auto-columns:\s*minmax\([^;]+\);",
        styles,
        flags=re.DOTALL,
    )
    assert not re.search(
        r"\.nav\s*\{[^}]*grid-template-columns:\s*repeat\(\d+",
        styles,
        flags=re.DOTALL,
    )


def test_mobile_content_inset_tracks_rendered_navigation_height():
    styles = STYLES.read_text(encoding="utf-8")
    layout = MOBILE_LAYOUT.read_text(encoding="utf-8")

    assert "--mobile-nav-height" in styles
    assert "--mobile-nav-height" in layout
    assert "ResizeObserver" in layout
    assert re.search(
        r"\.main\s*\{[^}]*padding-bottom:\s*calc\("
        r"var\(--mobile-nav-height",
        styles,
        flags=re.DOTALL,
    )


def test_mobile_topbar_actions_are_full_width_and_keep_dom_order():
    styles = STYLES.read_text(encoding="utf-8")

    assert re.search(
        r"\.topbar-side\s*\{[^}]*width:\s*100%;"
        r"[^}]*align-items:\s*stretch;"
        r"[^}]*flex-direction:\s*column;",
        styles,
        flags=re.DOTALL,
    )
    assert re.search(
        r"\.topbar-side\s+\.actions\s*\{[^}]*width:\s*100%;"
        r"[^}]*display:\s*grid;",
        styles,
        flags=re.DOTALL,
    )
    assert ".topbar-side .actions button, .topbar-side > button { width: 100%; }" in styles
    assert "flex-direction: column-reverse" not in styles
    assert re.search(
        r"\.topbar-side\s+\.actions\s+\.primary-button\s*\{[^}]*order:\s*-1;",
        styles,
        flags=re.DOTALL,
    )


def test_public_profile_definition_list_uses_shared_card_layout():
    styles = STYLES.read_text(encoding="utf-8")

    assert ".client-public-profile-summary" in styles
    assert re.search(
        r"\.client-card\s+dl,\s*\.client-public-profile-summary\s*\{"
        r"[^}]*display:\s*grid;",
        styles,
        flags=re.DOTALL,
    )
    assert re.search(
        r"\.client-card\s+dd,\s*\.client-public-profile-summary\s+dd\s*\{"
        r"[^}]*margin:\s*0;",
        styles,
        flags=re.DOTALL,
    )


def test_public_profile_form_is_contained_on_mobile():
    clients = CLIENTS.read_text(encoding="utf-8")

    assert re.search(
        r"\.client-public-profile-panel\s*\{[^}]*min-width:\s*0;"
        r"[^}]*overflow:\s*hidden;",
        clients,
        flags=re.DOTALL,
    )
    assert re.search(
        r"\.client-public-profile-form\s+label\s*\{[^}]*display:\s*grid;"
        r"[^}]*min-width:\s*0;",
        clients,
        flags=re.DOTALL,
    )
    assert re.search(
        r"\.client-public-profile-form\s+input\s*\{[^}]*width:\s*100%;"
        r"[^}]*min-width:\s*0;",
        clients,
        flags=re.DOTALL,
    )
    assert re.search(
        r"@media\s*\(max-width:\s*760px\)[\s\S]*"
        r"\.client-public-profile-form\s+\.client-invite-actions\s*\{"
        r"[^}]*grid-template-columns:\s*1fr;",
        clients,
    )
