from pathlib import Path

from app.models import User

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"


def test_user_model_maps_nullable_timezone_column():
    column = User.__table__.c.timezone

    assert column.nullable is True
    assert column.type.length == 64


def test_timezone_preference_has_isolated_get_and_put_contract():
    api_source = (APP / "api" / "onboarding.py").read_text(encoding="utf-8")
    service_source = (APP / "services" / "preferences.py").read_text(encoding="utf-8")

    assert '@router.get("/preferences/timezone"' in api_source
    assert '@router.put("/preferences/timezone"' in api_source
    assert "owner_timezone_name(session, identity.user_id)" in service_source
    assert "user.timezone = body.timezone" in service_source


def test_web_session_timezone_is_explicit_opt_in_for_backward_compatibility():
    api_source = (APP / "api" / "web_auth.py").read_text(encoding="utf-8")
    js_source = (APP / "web_static" / "app.js").read_text(encoding="utf-8")

    assert "include_timezone: bool = False" in api_source
    assert "owner_timezone_name(session, owner_user_id)" in api_source
    assert "/web/api/auth/session?include_timezone=true" in js_source
    assert "state.timezone = session.timezone" in js_source


def test_reservation_day_off_check_uses_owner_timezone():
    source = (APP / "services" / "scheduling_common.py").read_text(encoding="utf-8")

    assert "timezone = owner_timezone(session, owner_user_id)" in source
    assert "reservation.starts_at.astimezone(timezone).date()" in source


def test_client_projection_exposes_effective_owner_timezone():
    schema_source = (APP / "schemas" / "client_contour.py").read_text(encoding="utf-8")
    service_source = (APP / "services" / "client_contour.py").read_text(encoding="utf-8")

    assert "timezone: str" in schema_source
    assert "timezone=owner_timezone_name(session, row.owner_user_id)" in service_source
