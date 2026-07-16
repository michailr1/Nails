import json

from nails_scheduling import tools

CLIENT = {
    "id": "hidden-id",
    "public_name": "Татьяна",
    "phone": "+34 600 000 000",
    "private_alias": "сложные ногти",
    "contact_channel": "Telegram",
    "birthday": None,
    "notes": None,
    "nail_skin_notes": "Тонкая ногтевая пластина",
    "sensitivity_notes": None,
    "style_preferences": "Зелёный цвет",
    "communication_preferences": "На вы",
}


def _set_context(monkeypatch):
    monkeypatch.setattr(tools, "_trusted_telegram_user_id", lambda: "700000001")
    monkeypatch.setattr(tools, "_api_key", lambda: "k" * 64)


def test_list_clients_calls_owner_endpoint_and_hides_internal_id(monkeypatch):
    _set_context(monkeypatch)
    calls = []

    def fake_backend(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "result": {"clients": [CLIENT]}}

    monkeypatch.setattr(tools, "_call_backend", fake_backend)
    result = json.loads(tools.nails_scheduling({"action": "list_clients"}))

    assert result["ok"] is True
    assert result["action"] == "list_clients"
    assert calls == [
        {
            "action": "list_clients",
            "telegram_user_id": "700000001",
            "api_key": "k" * 64,
            "method": "GET",
            "path": "/api/v1/scheduling/clients",
            "params": None,
            "json_body": None,
        }
    ]
    assert result["result"]["clients"][0]["public_name"] == "Татьяна"
    assert "id" not in result["result"]["clients"][0]


def test_list_clients_accepts_empty_result(monkeypatch):
    _set_context(monkeypatch)
    monkeypatch.setattr(
        tools,
        "_call_backend",
        lambda **kwargs: {"ok": True, "result": {"clients": []}},
    )

    result = json.loads(tools.nails_scheduling({"action": "list_clients"}))

    assert result == {
        "ok": True,
        "action": "list_clients",
        "result": {"clients": []},
    }
