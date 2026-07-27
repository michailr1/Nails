from __future__ import annotations

from datetime import date

import pytest

from app.client_bot import (
    BotConfig,
    ClientBotConfigError,
    base_services,
    date_picker_keyboard,
    format_catalog,
    format_service_price,
    master_menu_keyboard,
    master_picker_keyboard,
    parse_start_token,
    service_picker_keyboard,
    telegram_public_name,
)

BINDING_A = "11111111-1111-4111-8111-111111111111"
BINDING_B = "22222222-2222-4222-8222-222222222222"


def _master(binding_id: str, name: str) -> dict[str, str | None]:
    return {
        "binding_id": binding_id,
        "display_name": name,
        "public_contact": None,
    }


def _catalog() -> dict[str, object]:
    return {
        "master": _master(BINDING_A, "Ногти у Насти"),
        "services": [
            {
                "public_name": "Маникюр",
                "kind": "base",
                "price_type": "fixed",
                "price_amount": "2700.00",
                "currency": "RUB",
                "category": "Маникюр",
            },
            {
                "public_name": "Снятие",
                "kind": "addon",
                "price_type": "fixed",
                "price_amount": "300.00",
                "currency": "RUB",
                "category": "Допы",
            },
        ],
    }


def test_parse_start_token_supports_telegram_command_suffix():
    assert parse_start_token("/start opaque-token") == "opaque-token"
    assert parse_start_token("/start@client_bot opaque-token") == "opaque-token"
    assert parse_start_token("/start") is None
    assert parse_start_token("/menu") is None


def test_client_public_name_uses_client_identity_only():
    assert telegram_public_name({"first_name": "Анна", "last_name": "Иванова"}) == (
        "Анна Иванова"
    )
    assert telegram_public_name({"username": "anna"}) == "@anna"
    assert telegram_public_name({}) == "Клиентка"


def test_master_picker_exposes_binding_handle_not_master_telegram_id():
    keyboard = master_picker_keyboard(
        [_master(BINDING_A, "Мастер А"), _master(BINDING_B, "Мастер Б")]
    )
    serialized = str(keyboard)
    assert f"master:{BINDING_A}" in serialized
    assert f"master:{BINDING_B}" in serialized
    assert "telegram_user_id" not in serialized
    assert "7132701825" not in serialized


def test_master_menu_callback_data_stays_within_telegram_limit():
    keyboard = master_menu_keyboard(_master(BINDING_A, "Мастер А"))
    callbacks = [
        button["callback_data"]
        for row in keyboard["inline_keyboard"]
        for button in row
    ]
    assert callbacks == [f"price:{BINDING_A}", f"book:{BINDING_A}", "masters"]
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks)


def test_price_formatting_uses_public_price_contract():
    assert format_service_price(
        {"price_type": "fixed", "price_amount": "2700.00", "currency": "RUB"}
    ) == "2 700 ₽"
    assert format_service_price(
        {
            "price_type": "range",
            "price_min_amount": "2500",
            "price_max_amount": "3000",
            "currency": "RUB",
        }
    ) == "2 500–3 000 ₽"
    assert format_service_price(
        {
            "price_type": "per_unit",
            "price_amount": "100",
            "price_unit": "ноготь",
            "currency": "RUB",
        }
    ) == "100 ₽ / ноготь"
    assert format_service_price({"price_type": "on_request", "currency": "RUB"}) == (
        "цена уточняется"
    )


def test_catalog_contains_only_public_projection():
    text = format_catalog(_catalog())
    assert "Ногти у Насти" in text
    assert "Маникюр — 2 700 ₽" in text
    assert "Снятие — 300 ₽" in text
    assert "owner_user_id" not in text
    assert "telegram_user_id" not in text


def test_service_and_date_picker_keep_owner_out_of_callback_contract():
    catalog = _catalog()
    service_keyboard = service_picker_keyboard(catalog)
    callbacks = [
        button["callback_data"]
        for row in service_keyboard["inline_keyboard"]
        for button in row
    ]
    assert f"svc:{BINDING_A}:0" in callbacks
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks)

    dates = date_picker_keyboard(BINDING_A, 0, today=date(2026, 7, 28))
    date_callbacks = [
        button["callback_data"]
        for row in dates["inline_keyboard"]
        for button in row
        if button["callback_data"].startswith("day:")
    ]
    assert date_callbacks[0] == f"day:{BINDING_A}:0:20260728"
    assert len(date_callbacks) == 14
    assert all(len(value.encode("utf-8")) <= 64 for value in date_callbacks)


def test_base_services_excludes_addons():
    services = base_services(_catalog())
    assert [service["public_name"] for service in services] == ["Маникюр"]


def test_bot_config_requires_token_and_separate_client_key(monkeypatch):
    monkeypatch.delenv("CLIENT_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("CLIENT_INTERNAL_API_KEY", "c" * 64)
    with pytest.raises(ClientBotConfigError, match="CLIENT_TELEGRAM_BOT_TOKEN"):
        BotConfig.from_env()

    monkeypatch.setenv("CLIENT_TELEGRAM_BOT_TOKEN", "123:test")
    monkeypatch.setenv("CLIENT_INTERNAL_API_KEY", "short")
    with pytest.raises(ClientBotConfigError, match="CLIENT_INTERNAL_API_KEY"):
        BotConfig.from_env()
