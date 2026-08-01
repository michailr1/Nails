from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "backend" / "app" / "web_static" / "index.html"
PROFILE_JS = ROOT / "backend" / "app" / "web_static" / "web-public-profile-visible.js"


def test_profile_overlay_loads_after_reachability_script():
    source = INDEX.read_text(encoding="utf-8")
    reachability = source.index("/web/web-client-reachability.js")
    profile = source.index("/web/web-public-profile-visible.js")
    assert profile > reachability


def test_ready_profile_remains_visible_and_editable():
    source = PROFILE_JS.read_text(encoding="utf-8")
    assert "Как вас увидят клиентки" in source
    assert "profile.display_name" in source
    assert "profile.public_contact" in source
    assert "data-edit-public-profile" in source
    assert ">Изменить<" in source
    assert ">Сохранить<" in source
    assert "data-cancel-public-profile" in source
    assert 'api("/web/api/client-linking/public-profile"' in source
    assert 'method: "PUT"' in source


def test_missing_profile_still_uses_blocking_setup():
    source = PROFILE_JS.read_text(encoding="utf-8")
    assert "Перед приглашением" in source
    assert "Сохранить и продолжить" in source
    assert 'required placeholder="Например, Настя"' in source
