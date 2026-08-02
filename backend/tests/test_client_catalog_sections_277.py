from __future__ import annotations

import uuid
from pathlib import Path

from app.client_bot_booking_flow import draft_addon_keyboard
from app.client_bot_catalog_sections import (
    PAGE_SIZE,
    callbacks,
    catalog_categories,
    category_page,
    category_picker_keyboard,
    format_duration,
    short_service_name,
)

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
BINDING_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))


def _service(name: str, category: str, *, kind: str = "base") -> dict[str, object]:
    return {
        "public_name": name,
        "category": category,
        "kind": kind,
        "price_type": "fixed",
        "price_amount": 2100,
        "price_min_amount": None,
        "price_max_amount": None,
        "price_unit": None,
        "currency": "RUB",
        "duration_minutes": 130,
        "extra_minutes": 15,
    }


def _catalog() -> dict[str, object]:
    return {
        "master": {"binding_id": BINDING_ID, "display_name": "Настя"},
        "services": [
            _service("Маникюр классический", "Маникюр"),
            _service("Маникюр европейский", "Маникюр"),
            _service("Маникюр с гель-лаком", "Маникюр"),
            _service("Маникюр с укреплением", "Маникюр"),
            _service("Маникюр без покрытия", "Маникюр"),
            _service("Маникюр аппаратный", "Маникюр"),
            _service("Маникюр комбинированный", "Маникюр"),
            _service("Педикюр классический", "Педикюр"),
            _service("Снятие", "Маникюр", kind="addon"),
        ],
    }


def test_booking_starts_with_categories_not_flat_services():
    catalog = _catalog()
    keyboard = category_picker_keyboard(catalog, mode="book")

    assert catalog_categories(catalog, mode="book") == ["Маникюр", "Педикюр"]
    labels = [button[0]["text"] for button in keyboard["inline_keyboard"][:-2]]
    assert labels == ["Маникюр", "Педикюр"]
    assert "Маникюр с гель-лаком" not in labels
    assert keyboard["inline_keyboard"][-2][0]["text"] == "Не знаю, подскажите"


def test_category_page_has_at_most_six_readable_buttons():
    text, keyboard = category_page(
        _catalog(), category_index=0, page=0, mode="book"
    )
    service_buttons = [
        row[0]
        for row in keyboard["inline_keyboard"]
        if row and str(row[0].get("callback_data", "")).startswith("svc:")
    ]

    assert len(service_buttons) == PAGE_SIZE
    assert all(len(button["text"]) <= 48 for button in service_buttons)
    assert any(button["text"].endswith("С гель-лаком") for button in service_buttons)
    assert "2 100 ₽" in text
    assert "~2 ч 10 мин" in text
    assert "Маникюр с гель-лаком" not in text
    assert "С гель-лаком" in text


def test_category_page_paginates_instead_of_flattening_catalog():
    _, first = category_page(_catalog(), category_index=0, page=0, mode="book")
    second_callback = next(
        value
        for value in callbacks(first)
        if value.startswith("cat:") and value.endswith(":1")
    )
    assert len(second_callback.encode()) <= 64

    text, second = category_page(
        _catalog(), category_index=0, page=1, mode="book"
    )
    assert "1. Комбинированный" in text
    service_callbacks = [
        value for value in callbacks(second) if value.startswith("svc:")
    ]
    assert len(service_callbacks) == 1


def test_price_is_also_opened_by_sections_and_lists_addons():
    catalog = _catalog()
    assert catalog_categories(catalog, mode="price") == ["Маникюр", "Педикюр"]
    text, keyboard = category_page(
        catalog, category_index=0, page=1, mode="price"
    )

    assert "Снятие" in text
    assert not any(value.startswith("svc:") for value in callbacks(keyboard))
    assert any(value.startswith("price:") for value in callbacks(keyboard))


def test_short_name_removes_only_repeated_category_prefix():
    assert (
        short_service_name(
            _service("Маникюр с гель-лаком", "Маникюр"), "Маникюр"
        )
        == "С гель-лаком"
    )
    assert (
        short_service_name(
            _service("Покрытие гель-лаком", "Маникюр"), "Маникюр"
        )
        == "Покрытие гель-лаком"
    )
    assert format_duration({"duration_minutes": 60}) == "~1 ч"
    assert format_duration({"duration_minutes": 45}) == "~45 мин"


def test_addons_remain_optional():
    draft = {
        "draft_id": str(uuid.uuid4()),
        "addon_names": [],
        "addon_quantities": {},
        "addons": [{"public_name": "Снятие", "quantity_supported": False}],
        "master": {"binding_id": BINDING_ID},
    }
    keyboard = draft_addon_keyboard(draft)

    assert keyboard["inline_keyboard"][-2][0] == {
        "text": "Продолжить",
        "callback_data": f"dates:{draft['draft_id']}",
    }


def test_help_uses_existing_contact_forward_and_not_a_new_domain_model():
    onboarding = (APP / "client_bot_onboarding.py").read_text(encoding="utf-8")
    runtime_api = (APP / "client_bot_runtime_api.py").read_text(encoding="utf-8")

    assert '"Не знаю, подскажите"' in (
        APP / "client_bot_catalog_sections.py"
    ).read_text(encoding="utf-8")
    assert ".contact_forward(" in onboarding
    assert '"/api/v1/client/contact-forward"' in runtime_api
    assert "Клиентка не уверена, какую процедуру выбрать" in onboarding
