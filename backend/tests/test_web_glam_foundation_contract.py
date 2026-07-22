from pathlib import Path


WEB_STATIC = Path(__file__).resolve().parents[1] / "app" / "web_static"
FONT_PATH = "/web/fonts/cormorant-garamond-cyrillic-500-normal.woff2"
GLAM_TOKENS = (
    "--bg-2:",
    "--surface-2:",
    "--blush-deep:",
    "--blush-tint:",
    "--gold:",
    "--gold-lite:",
    "--blob-rose:",
    "--blob-peach:",
    "--blob-gold:",
    "--serif:",
    "--ring:",
    "--shadow-soft:",
)


def test_document_supports_light_and_dark_color_schemes() -> None:
    html = (WEB_STATIC / "index.html").read_text(encoding="utf-8")

    assert "<meta name=\"color-scheme\" content=\"light dark\" />" in html
    assert "media=\"(prefers-color-scheme: light)\"" in html
    assert "media=\"(prefers-color-scheme: dark)\"" in html
    assert "href=\"/web/design-system.css\"" in html


def test_soft_glam_tokens_and_theme_overrides_are_present() -> None:
    css = (WEB_STATIC / "design-system.css").read_text(encoding="utf-8")

    assert all(token in css for token in GLAM_TOKENS)
    assert "@media (prefers-color-scheme: dark)" in css
    assert ":root[data-theme=\"dark\"]" in css
    assert ":root[data-theme=\"light\"]" in css
    assert "background-attachment: fixed" in css


def test_foundation_has_no_external_font_or_cdn_dependency() -> None:
    css = (WEB_STATIC / "design-system.css").read_text(encoding="utf-8")
    html = (WEB_STATIC / "index.html").read_text(encoding="utf-8")
    combined = (css + "\n" + html).lower()

    assert "https://" not in combined
    assert "http://" not in combined
    assert "fonts.googleapis" not in combined
    assert "fonts.gstatic" not in combined
    assert FONT_PATH in css
    assert "font-display: swap" in css


def test_mobile_accessibility_contract_is_present() -> None:
    css = (WEB_STATIC / "design-system.css").read_text(encoding="utf-8")

    assert "overflow-x: clip" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "min-height: 44px" in css
    assert ":focus-visible" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
