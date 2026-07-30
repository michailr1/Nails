from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services import web_client_linking

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"
API = ROOT / "backend" / "app" / "api"


def test_invitation_link_is_built_from_backend_configuration(monkeypatch):
    monkeypatch.setattr(
        web_client_linking,
        "get_settings",
        lambda: SimpleNamespace(client_telegram_bot_username="configured_client_bot"),
    )
    assert web_client_linking.client_invitation_url("abc_123") == (
        "https://t.me/configured_client_bot?start=abc_123"
    )
    assert "Нэйли" not in web_client_linking.invitation_copy(
        "https://t.me/configured_client_bot?start=abc_123"
    )


def test_invitation_link_does_not_exist_without_configured_username(monkeypatch):
    monkeypatch.setattr(
        web_client_linking,
        "get_settings",
        lambda: SimpleNamespace(client_telegram_bot_username=""),
    )
    assert web_client_linking.client_invitation_url("abc_123") is None


def test_cabinet_js_does_not_hardcode_client_bot_or_expose_raw_token():
    source = (WEB / "web-client-reachability.js").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "naily_client_bot" not in lowered
    assert "invitation_start_token" not in source
    assert "персональный код приглашения" not in lowered
    assert "код ссылки для записи" not in lowered
    assert "payload.token" not in source
    assert "invitation_url" in source


def test_invitation_ui_has_no_prompt_alert_or_sent_log():
    source = (WEB / "web-client-reachability.js").read_text(encoding="utf-8")
    assert "window.prompt" not in source
    assert "window.alert" not in source
    assert "История сообщений" not in source
    assert "showSentClientLog" not in source
    assert "/web/api/client-linking/sent" not in source
    assert "Скопировать" in source


def test_reachability_language_matches_master_vocabulary():
    source = (WEB / "web-client-reachability.js").read_text(encoding="utf-8")
    assert "Кому можно написать" in source
    assert "На связи в Telegram" in source
    assert "Сообщения не доходят" in source
    assert "Нет в Telegram" in source
    assert "ещё не проверено" not in source
    assert "Только подключённые" not in source
    assert "Можно получать сообщения Нэйли" not in source


def test_connected_filter_uses_backend_result_without_dom_pruning():
    source = (WEB / "web-client-reachability.js").read_text(encoding="utf-8")
    assert "/web/api/clients?connected_only=true" in source
    assert "allowed = new Set" not in source
    assert "!allowed.has" not in source


def test_requests_live_in_calendar_not_top_level_navigation():
    source = (WEB / "web-client-requests.js").read_text(encoding="utf-8")
    assert 'data-view="client-requests"' not in source
    assert "originalAppShellForClientRequests" not in source
    assert "просят записаться" in source
    assert "client-request-summary-row" in source
    assert "client-request-day-marker" in source
    assert "decorateClientCardsWithRequests" in source


def test_sent_log_endpoint_removed_and_personal_web_response_hides_token():
    source = (API / "web_client_linking.py").read_text(encoding="utf-8")
    assert '@router.get("/sent"' not in source
    assert "list_sent_notifications" not in source
    assert "PersonalClientInviteResponse" in source
    assert "client_invitation_url(created.token)" in source


def test_client_bot_username_is_configuration_not_javascript():
    config = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert 'alias="CLIENT_TELEGRAM_BOT_USERNAME"' in config
    assert "CLIENT_TELEGRAM_BOT_USERNAME:" in compose
    assert "CLIENT_TELEGRAM_BOT_USERNAME=" in env
