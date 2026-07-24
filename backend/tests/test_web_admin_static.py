from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "web_static"


def test_admin_assets_are_loaded_after_base_app():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert '/web/web-admin-masters.css' in html
    assert html.index('/web/app.js') < html.index('/web/web-admin-masters.js')


def test_admin_view_has_role_gate_confirmation_and_masking():
    script = (STATIC_DIR / "web-admin-masters.js").read_text(encoding="utf-8")
    assert 'api("/web/api/admin/masters")' in script
    assert 'error.status === 403' in script
    assert 'window.confirm' in script
    assert 'maskTelegramId' in script
    assert 'data-view="masters"' in script
