from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"
APP = ROOT / "backend" / "app"


def test_initial_session_is_gated_until_route_is_restored():
    auth = (WEB / "web-auth-bootstrap.js").read_text(encoding="utf-8")
    nav = (WEB / "web-shell-navigation.js").read_text(encoding="utf-8")

    assert "let routeGateActive = true" in auth
    assert "challengeGateActive || routeGateActive" in auth
    assert "releaseRouteCheck" in auth
    assert "state.view = initialCabinetView" in nav
    assert "releaseRouteCheck()" in nav
    assert "initialCabinetViewChanged" not in nav


def test_reload_does_not_start_calendar_before_services_or_statistics():
    nav = (WEB / "web-shell-navigation.js").read_text(encoding="utf-8")
    auth = (WEB / "web-auth-bootstrap.js").read_text(encoding="utf-8")

    assert 'new Set(["calendar", "clients", "services", "statistics"])' in nav
    assert "gatedSessionRequest" in auth
    assert "nativeFetch(input, options).then(resolve, reject)" in auth
    assert nav.index("state.view = initialCabinetView") < nav.index("releaseRouteCheck()")


def test_client_menu_has_my_requests_and_write_master_actions():
    source = (APP / "client_bot_contact_actions.py").read_text(encoding="utf-8")

    assert "📁 Мои записи" in source
    assert "💬 Написать мастеру" in source
    assert 'callback_data": f"requests:{binding_id}"' in source
    assert 'callback_data": f"write:{binding_id}"' in source


def test_help_forward_contains_safe_telegram_contact_not_internal_ids():
    source = (APP / "client_bot_contact_actions.py").read_text(encoding="utf-8")

    assert "@{username} · Telegram ID {telegram_user_id}" in source
    assert "Telegram ID {telegram_user_id}" in source
    assert "owner_user_id" not in source
    assert "client_id" not in source
    assert "Контакт:" in source


def test_one_message_flow_is_limited_and_informational_only():
    source = (APP / "client_bot_contact_actions.py").read_text(encoding="utf-8")

    assert "MAX_CLIENT_MESSAGE_LENGTH = 500" in source
    assert "Оно не изменит услугу, время или цену заявки" in source
    assert "Сообщение передано мастеру. Оно не меняет параметры заявки." in source
    assert ".contact_forward(" in source
    assert ".update_booking_draft" not in source
    assert ".select_booking_draft_slot" not in source
    assert ".submit_draft" not in source


def test_request_list_uses_existing_api_and_cancel_callbacks_fit_telegram():
    runtime = (APP / "client_bot_runtime_api.py").read_text(encoding="utf-8")
    source = (APP / "client_bot_contact_actions.py").read_text(encoding="utf-8")

    assert '"/api/v1/client/requests"' in runtime
    assert 'f"/api/v1/client/requests/{request_id}/cancel"' in runtime
    assert 'f"cancelreq:{request_id}"' in source
    assert 'f"cancelreq:{binding_id}:{item.get(' not in source
    assert "_request_bindings" in source


def test_runtime_uses_contact_aware_bot():
    source = (APP / "client_bot_v1.py").read_text(encoding="utf-8")

    assert "from app.client_bot_contact_actions import ContactAwareOnboardingBot" in source
    assert "bot = ContactAwareOnboardingBot(telegram, nails)" in source
