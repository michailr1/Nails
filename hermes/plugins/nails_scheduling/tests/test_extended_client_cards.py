import json

from nails_scheduling import client_cards, presenters, tools, transport

CARD = {
    "action": "create_client",
    "client_public_name": "Анна Тестовая",
    "phone": "+34 600 000 000",
    "private_alias": "Анна сложные ногти",
    "contact_channel": "Telegram",
    "birthday": "1990-05-12",
    "notes": "Предпочитает вечерние записи",
    "nail_skin_notes": "Тонкая ногтевая пластина",
    "sensitivity_notes": "Чувствительность к резким запахам",
    "style_preferences": "Короткий миндаль, молочные оттенки",
    "communication_preferences": "Писать без звонков",
    "confirmed": True,
}


def _backend_card():
    return {
        "id": "hidden-id",
        "public_name": CARD["client_public_name"],
        "phone": CARD["phone"],
        "private_alias": CARD["private_alias"],
        "contact_channel": CARD["contact_channel"],
        "birthday": CARD["birthday"],
        "notes": CARD["notes"],
        "nail_skin_notes": CARD["nail_skin_notes"],
        "sensitivity_notes": CARD["sensitivity_notes"],
        "style_preferences": CARD["style_preferences"],
        "communication_preferences": CARD["communication_preferences"],
    }


def test_extended_client_card_is_sent_to_backend(monkeypatch):
    calls = []

    def fake_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "find_client":
            return {"ok": True, "result": {"found": False, "client": None}}
        return {
            "ok": True,
            "result": {
                "client": _backend_card(),
                "created": True,
                "contact_added": False,
            },
        }

    monkeypatch.setattr(transport, "_call_backend", fake_backend)
    values = client_cards.validate_client_card_args(CARD)

    result = client_cards.create_client_card(
        values,
        telegram_user_id="700000001",
        api_key="k" * 64,
    )

    assert result["ok"] is True
    body = calls[1]["json_body"]
    assert body["public_name"] == CARD["client_public_name"]
    for field in (
        "phone",
        "private_alias",
        "contact_channel",
        "birthday",
        "notes",
        "nail_skin_notes",
        "sensitivity_notes",
        "style_preferences",
        "communication_preferences",
    ):
        assert body[field] == CARD[field]


def test_client_presenter_keeps_private_fields_but_removes_id():
    result = presenters._sanitize_success(
        "find_client",
        {"found": True, "client": _backend_card()},
    )

    assert result["client"]["private_alias"] == CARD["private_alias"]
    assert result["client"]["style_preferences"] == CARD["style_preferences"]
    assert "id" not in result["client"]


def test_old_name_only_client_payload_remains_valid():
    values = client_cards.validate_client_card_args(
        {
            "action": "create_client",
            "client_public_name": "Анна",
            "confirmed": True,
        }
    )

    assert values["client_public_name"] == "Анна"
    for field in (
        "phone",
        "private_alias",
        "contact_channel",
        "birthday",
        "notes",
        "nail_skin_notes",
        "sensitivity_notes",
        "style_preferences",
        "communication_preferences",
    ):
        assert values[field] is None


def test_tool_routes_create_client_to_extended_guard(monkeypatch):
    monkeypatch.setattr(tools, "_trusted_telegram_user_id", lambda: "700000001")
    monkeypatch.setattr(tools, "_api_key", lambda: "k" * 64)
    captured = {}

    def fake_create(values, **kwargs):
        captured.update(values)
        return {
            "ok": True,
            "result": {
                "client": _backend_card(),
                "created": True,
                "contact_added": False,
            },
        }

    monkeypatch.setattr(tools, "create_client_card", fake_create)

    result = json.loads(tools.nails_scheduling(CARD))

    assert result["ok"] is True
    assert captured["sensitivity_notes"] == CARD["sensitivity_notes"]
    assert result["result"]["client"]["communication_preferences"] == CARD[
        "communication_preferences"
    ]
