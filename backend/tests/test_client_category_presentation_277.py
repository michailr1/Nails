from __future__ import annotations

from app.client_bot_catalog_sections import (
    catalog_categories,
    category_page,
    category_picker_keyboard,
)

BINDING_ID = "11111111-1111-4111-8111-111111111111"


def _service(
    name: str,
    category: str,
    *,
    kind: str,
    price: int = 1000,
    duration: int = 60,
) -> dict[str, object]:
    return {
        "public_name": name,
        "category": category,
        "kind": kind,
        "price_type": "fixed",
        "price_amount": price,
        "currency": "RUB",
        "duration_minutes": duration,
    }


def _payload() -> dict[str, object]:
    # Intentionally mirrors the problematic first-seen order from the live bot:
    # technical/additional categories arrive before primary client intents.
    return {
        "master": {"binding_id": BINDING_ID},
        "services": [
            _service(
                "Снятие покрытия без последующей процедуры",
                "Дополнительно",
                kind="base",
                price=300,
                duration=30,
            ),
            _service("Дизайн френч", "Дизайн", kind="addon", price=500, duration=15),
            _service("Маникюр классический", "Маникюр", kind="base", price=2000),
            _service(
                "Парафинотерапия",
                "Парафинотерапия",
                kind="addon",
                price=600,
                duration=20,
            ),
            _service("Педикюр классический", "Педикюр", kind="base", price=2500),
        ],
    }


def _button_texts(keyboard: dict[str, object]) -> list[str]:
    return [
        str(button["text"])
        for row in keyboard["inline_keyboard"]  # type: ignore[index]
        for button in row
    ]


def test_booking_shows_primary_intents_first_and_additional_services_last() -> None:
    payload = _payload()

    assert catalog_categories(payload, mode="book") == [
        "Маникюр",
        "Педикюр",
        "Дополнительно",
    ]

    labels = _button_texts(category_picker_keyboard(payload, mode="book"))
    assert labels[:3] == [
        "Маникюр",
        "Педикюр",
        "Снятие и другие услуги",
    ]
    assert "Дополнительно" not in labels

    text, _keyboard = category_page(
        payload,
        category_index=2,
        page=0,
        mode="book",
    )
    assert text.startswith("Снятие и другие услуги\n")
    assert "Снятие покрытия без последующей процедуры" in text


def test_price_uses_clear_label_and_keeps_additional_section_last() -> None:
    payload = _payload()

    assert catalog_categories(payload, mode="price") == [
        "Маникюр",
        "Педикюр",
        "Дизайн",
        "Парафинотерапия",
        "Дополнительно",
    ]

    labels = _button_texts(category_picker_keyboard(payload, mode="price"))
    assert labels[:5] == [
        "Маникюр",
        "Педикюр",
        "Дизайн",
        "Парафинотерапия",
        "Дополнительные услуги",
    ]
    assert "Дополнительно" not in labels

    text, _keyboard = category_page(
        payload,
        category_index=4,
        page=0,
        mode="price",
    )
    assert text.startswith("Дополнительные услуги\n")


def test_client_presentation_does_not_mutate_catalog_categories() -> None:
    payload = _payload()
    original = [service["category"] for service in payload["services"]]  # type: ignore[index]

    category_picker_keyboard(payload, mode="book")
    category_picker_keyboard(payload, mode="price")

    assert [service["category"] for service in payload["services"]] == original  # type: ignore[index]
