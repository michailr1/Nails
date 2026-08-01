from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"
INDEX = WEB / "index.html"

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


def _linked_css_files() -> list[Path]:
    source = INDEX.read_text(encoding="utf-8")
    hrefs = re.findall(r'href="/web/([^\"]+\.css)"', source)
    return [WEB / href for href in hrefs]


def _defined_selectors(source: str) -> set[str]:
    selectors: set[str] = set()
    for match in SELECTOR_BLOCK.finditer(source):
        prelude = match.group(1).strip()
        if prelude.startswith("@"):
            continue
        for selector in prelude.split(","):
            selectors.add(selector.strip())
    return selectors


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
