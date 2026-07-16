import json

import pytest
from nails_scheduling import client_cards, tools

CURRENT_CARD = {
    "id": "hidden-id",
    "public_name": "Кристина",
    "phone": "+34 600 000 000",
    "private_alias": None,
    "contact_channel": "Telegram",
    "birthday": None,
    "notes": None,
    "nail_skin_notes": "Тонкая ногтевая пластина",
    "sensitivity_notes": None,
    "style_preferences": None,
    "communication_preferences": None,
}


def test_update_existing_client_merges_only_supplied_fields(monkeypatch):
    calls = []

    def fake_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "find_client":
            return {"ok": True, "result": {"found": True, "client": CURRENT_CARD}}
        updated = {
            **CURRENT_CARD,
            "notes": "Курит",
            "style_preferences": "Любит зелёный цвет и яркий дизайн",
            "communication_preferences": "На вы",
        }
        return {
            "ok": True,
            "result": {
                "client": updated,
                "changed": True,
                "changed_fields": [
                    "communication_preferences",
                    "notes",
                    "style_preferences",
                ],
            },
        }

    monkeypatch.setattr(client_cards, "_call_backend", fake_backend)
    values = client_cards.validate_client_card_update_args(
        {
            "action": "update_client",
            "client_public_name": "Кристина",
            "notes": "курит",
            "style_preferences": "любит зелёный цвет и яркий дизайн",
            "communication_preferences": "на вы",
            "confirmed": True,
        }
    )

    result = client_cards.update_client_card(
        values,
        telegram_user_id="700000001",
        api_key="k" * 64,
    )

    assert result["ok"] is True
    body = calls[1]["json_body"]
    assert calls[1]["method"] == "PUT"
    assert calls[1]["path"] == "/api/v1/scheduling/clients"
    assert body["current_public_name"] == "Кристина"
    assert body["public_name"] == "Кристина"
    assert body["phone"] == CURRENT_CARD["phone"]
    assert body["contact_channel"] == CURRENT_CARD["contact_channel"]
    assert body["nail_skin_notes"] == CURRENT_CARD["nail_skin_notes"]
    assert body["notes"] == "курит"
    assert body["style_preferences"] == "любит зелёный цвет и яркий дизайн"
    assert body["communication_preferences"] == "на вы"
    assert "id" not in body
    assert "id" not in result["result"]["client"]


def test_update_client_allows_explicit_field_clear():
    values = client_cards.validate_client_card_update_args(
        {
            "action": "update_client",
            "client_public_name": "Кристина",
            "notes": None,
            "confirmed": True,
        }
    )

    assert values["updates"] == {"notes": None}


def test_update_client_requires_at_least_one_changed_field():
    with pytest.raises(client_cards.ToolInputError):
        client_cards.validate_client_card_update_args(
            {
                "action": "update_client",
                "client_public_name": "Кристина",
                "confirmed": True,
            }
        )


def test_tool_routes_update_client_and_returns_safe_result(monkeypatch):
    monkeypatch.setattr(tools, "_trusted_telegram_user_id", lambda: "700000001")
    monkeypatch.setattr(tools, "_api_key", lambda: "k" * 64)
    captured = {}

    def fake_update(values, **kwargs):
        captured.update(values)
        return {
            "ok": True,
            "result": {
                "client": {
                    key: value for key, value in CURRENT_CARD.items() if key != "id"
                },
                "changed": True,
                "changed_fields": ["notes"],
            },
        }

    monkeypatch.setattr(tools, "update_client_card", fake_update)
    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "update_client",
                "client_public_name": "Кристина",
                "notes": "курит",
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["action"] == "update_client"
    assert captured["updates"] == {"notes": "курит"}
    assert result["result"]["changed_fields"] == ["notes"]
    assert "id" not in result["result"]["client"]
