from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB_STATIC = ROOT / "backend" / "app" / "web_static"


def test_web001e_copy_does_not_shadow_auth_bootstrap_helper():
    auth_bootstrap = (WEB_STATIC / "web-auth-bootstrap.js").read_text(encoding="utf-8")
    login_copy = (WEB_STATIC / "web001e-copy.js").read_text(encoding="utf-8")

    assert "function releaseInitialSessionCheck()" in auth_bootstrap
    assert "function releaseInitialSessionCheck()" not in login_copy
    assert "function releaseLoginSessionCheck()" in login_copy
    assert "releaseLoginSessionCheck();" in login_copy
