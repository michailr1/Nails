from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"


def test_narrow_mobile_nav_is_fixed_four_column_grid():
    css = (WEB / "web-mobile-stability.css").read_text(encoding="utf-8")

    nav = css.split(".sidebar > .nav {", 1)[1].split("}", 1)[0]
    button = css.split(".sidebar .tab-button {", 1)[1].split("}", 1)[0]
    sidebar = css.split(".app-shell > .sidebar {", 1)[1].split("}", 1)[0]

    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in nav
    assert "grid-auto-flow: row" in nav
    assert "overflow: visible" in nav
    assert "min-width: 0" in button
    assert "white-space: nowrap" in button
    assert "font-size: clamp(.66rem, 2.8vw, .8rem)" in button
    assert "padding: 8px 10px" in sidebar
    assert "bottom: calc(12px + env(safe-area-inset-bottom))" in sidebar


def test_invite_buttons_recover_through_public_profile_setup():
    js = (WEB / "web-personal-link.js").read_text(encoding="utf-8")

    assert "openRequiredPublicProfile" in js
    assert 'button.dataset.publicProfileReady === "false"' in js
    assert "button.disabled = false" in js
    assert "decorateClientCardsWithRecoverableInvite" in js
    assert "renderReachabilityControlsWithRecoverableInvite" in js
    assert "showGeneralInvitationWithProfileRecovery" in js
    assert 'error.message === "master_public_profile_required"' in js


def test_profile_save_refreshes_client_invite_state_without_reload():
    js = (WEB / "web-public-profile-visible.js").read_text(encoding="utf-8")

    assert 'if (state.view === "clients") await renderClients()' in js
