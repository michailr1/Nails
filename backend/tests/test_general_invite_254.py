from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services import web_client_linking

ROOT = Path(__file__).resolve().parents[2]
WEB_JS = ROOT / "backend" / "app" / "web_static" / "web-client-reachability.js"
API = ROOT / "backend" / "app" / "api" / "web_client_linking.py"


class FakeSession:
    def __init__(self, scalar_result=None):
        self.scalar_result = scalar_result
        self.added = []
        self.commits = 0

    def scalar(self, _statement):
        return self.scalar_result

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


def configured_settings():
    return SimpleNamespace(client_telegram_bot_username="configured_client_bot")


def test_first_general_invite_creates_token_and_returns_ready_url(monkeypatch):
    monkeypatch.setattr(web_client_linking, "get_settings", configured_settings)
    monkeypatch.setattr(web_client_linking.secrets, "token_urlsafe", lambda _size: "new_token")
    session = FakeSession()
    identity = SimpleNamespace(user_id="owner-1")

    result = web_client_linking.get_or_create_general_invitation(session, identity)

    assert result == "https://t.me/configured_client_bot?start=new_token"
    assert len(session.added) == 1
    assert session.added[0].token == "new_token"
    assert session.added[0].owner_user_id == "owner-1"
    assert session.commits == 1


def test_repeated_general_invite_reuses_active_token(monkeypatch):
    monkeypatch.setattr(web_client_linking, "get_settings", configured_settings)
    session = FakeSession(scalar_result="existing_token")
    identity = SimpleNamespace(user_id="owner-1")

    first = web_client_linking.get_or_create_general_invitation(session, identity)
    second = web_client_linking.get_or_create_general_invitation(session, identity)

    assert first == second == "https://t.me/configured_client_bot?start=existing_token"
    assert session.added == []
    assert session.commits == 0


def test_general_invite_button_bootstraps_via_write_endpoint():
    source = WEB_JS.read_text(encoding="utf-8")
    assert "reachability.invitation_available" in source
    assert 'api("/web/api/client-linking/general-link"' in source
    assert 'method: "POST"' in source
    assert "reachability.invitation_url ?" not in source


def test_general_invite_endpoint_is_csrf_protected_write():
    source = API.read_text(encoding="utf-8")
    assert '@router.post("/general-link"' in source
    assert "validate_web_boundary(request)" in source
    assert "get_or_create_general_invitation(session, identity)" in source
