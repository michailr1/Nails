from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).parents[1] / "app" / "web_static"


def test_booking_edit_assets_are_loaded() -> None:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "web-booking.css").read_text(encoding="utf-8")

    assert "/web/web-booking.css" in index
    assert "/web/web-booking-edit.js" in index
    assert index.index("/web/app.js") < index.index("/web/web-booking-edit.js")
    assert "@media (max-width: 640px)" in css
    assert ".booking-edit-actions button" in css
    assert "background: var(--surface)" in css
    assert "color: var(--text)" in css
