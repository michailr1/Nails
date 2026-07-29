from __future__ import annotations

from datetime import date

from app.client_bot_booking_flow import (
    _composition_values,
    draft_addon_keyboard,
    draft_date_picker_keyboard,
    draft_slot_picker_keyboard,
    draft_summary_keyboard,
)

DRAFT_ID = "33333333-3333-4333-8333-333333333333"
BINDING_ID = "11111111-1111-4111-8111-111111111111"


def _draft():
    return {
        "draft_id": DRAFT_ID,
        "master": {"binding_id": BINDING_ID, "display_name": "Настя"},
        "service_name": "Маникюр",
        "addon_names": ["Ремонт"],
        "addon_quantities": {"ремонт": 2},
        "addons": [
            {
                "public_name": "Снятие",
                "quantity_supported": False,
            },
            {
                "public_name": "Ремонт",
                "quantity_supported": True,
            },
        ],
    }


def _callbacks(keyboard):
    return [
        button["callback_data"]
        for row in keyboard["inline_keyboard"]
        for button in row
    ]


def test_draft_callbacks_are_compact_and_do_not_carry_business_identity():
    callbacks = []
    callbacks += _callbacks(draft_addon_keyboard(_draft()))
    callbacks += _callbacks(
        draft_date_picker_keyboard(DRAFT_ID, today=date(2026, 8, 10))
    )
    callbacks += _callbacks(
        draft_slot_picker_keyboard(
            DRAFT_ID,
            ["2026-08-10T11:00:00+02:00"],
            selected_day=date(2026, 8, 10),
        )
    )
    callbacks += _callbacks(draft_summary_keyboard(DRAFT_ID))

    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks)
    draft_callbacks = [value for value in callbacks if DRAFT_ID in value]
    assert draft_callbacks
    serialized = " ".join(draft_callbacks)
    assert "owner_user_id" not in serialized
    assert "client_id" not in serialized
    assert "telegram_user_id" not in serialized
    assert "Маникюр" not in serialized
    assert "Ремонт" not in serialized


def test_quantity_controls_change_server_side_composition_values_only():
    draft = _draft()
    selected, quantities = _composition_values(
        draft,
        toggle_index=1,
        quantity_delta=1,
    )
    assert selected == ["Ремонт"]
    assert quantities == {"ремонт": 3}

    selected, quantities = _composition_values(
        {**draft, "addon_quantities": {"ремонт": 1}},
        toggle_index=1,
        quantity_delta=-1,
    )
    assert selected == ["Ремонт"]
    assert quantities == {"ремонт": 1}

    selected, quantities = _composition_values(draft, toggle_index=1)
    assert selected == []
    assert quantities == {}
