from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"


def test_master_settings_mobile_dialog_keeps_real_gutters_and_compact_controls():
    css = (WEB / "web-master-settings.css").read_text(encoding="utf-8")
    js = (WEB / "web-master-settings.js").read_text(encoding="utf-8")

    # Real-device regression from #304: the previous 6-10px shell gutters made
    # the bottom sheet look glued to the viewport edges.
    assert ".master-settings-backdrop" in css
    assert "padding: 18px;" in css
    assert "padding: 16px;" in css
    assert "width: 100%;" in css
    assert "padding: 20px;" in css
    assert "padding: 18px;" in css
    assert "calc(100vw - 20px)" not in css
    assert "calc(100vw - 12px)" not in css

    # Work hours read as one understandable setting rather than two unexplained
    # native inputs spanning edge-to-edge.
    assert "Рабочий день" in js
    assert "Обычно в это время Нэйли предлагает свободные окна" in js
    assert "Для отдельного дня время можно изменить в Календаре" in js
    assert "Начало" in js
    assert "Конец" in js
    assert ".master-work-hours-fields label" in css
    assert "border-radius: 14px;" in css
    assert "background: var(--surface-muted);" in css


def test_master_profile_reuses_corrected_mobile_shell():
    css = (WEB / "web-master-settings.css").read_text(encoding="utf-8")
    profile = (WEB / "web-public-profile-visible.js").read_text(encoding="utf-8")

    assert "master-settings-panel master-profile-panel" in profile
    assert ".master-profile-panel .client-public-profile-summary > div" in css
    assert "grid-template-columns: minmax(0, 1fr);" in css
    assert ".master-profile-panel [data-edit-public-profile]" in css
    assert "width: 100%;" in css


def test_account_menu_behavior_is_not_changed_by_mobile_visual_fix():
    js = (WEB / "web-master-settings.js").read_text(encoding="utf-8")

    assert "Профиль для клиенток" in js
    assert "data-open-master-settings" in js
    assert "data-master-logout" in js
    assert "confirmMasterLogout" in js
    assert 'document.addEventListener("keydown"' in js
    assert 'event.key !== "Escape"' in js
