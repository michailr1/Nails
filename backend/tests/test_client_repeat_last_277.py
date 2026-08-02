from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from app.client_bot_onboarding import client_menu_keyboard, repeat_draft_text
from app.services import client_repeat_last

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
BINDING_ID = "11111111-1111-1111-1111-111111111111"


def _context(*, client_id: str | None = "22222222-2222-2222-2222-222222222222"):
    return SimpleNamespace(
        owner_user_id="33333333-3333-3333-3333-333333333333",
        binding=SimpleNamespace(client_id=client_id, id=BINDING_ID),
        master=SimpleNamespace(binding_id=BINDING_ID),
    )


def test_repeat_last_is_the_first_menu_action_only_when_available():
    master = {"binding_id": BINDING_ID}

    available = client_menu_keyboard(
        master,
        show_masters=False,
        repeat_available=True,
    )
    unavailable = client_menu_keyboard(
        master,
        show_masters=False,
        repeat_available=False,
    )

    assert available["inline_keyboard"][0] == [
        {
            "text": "🔁 Как в прошлый раз",
            "callback_data": f"repeat:{BINDING_ID}",
        }
    ]
    assert all(
        button["text"] != "🔁 Как в прошлый раз"
        for row in unavailable["inline_keyboard"]
        for button in row
    )


def test_snapshot_composition_uses_existing_booking_snapshot():
    booking = SimpleNamespace(
        catalog_items_snapshot=[
            {"kind": "base", "public_name": "Маникюр с гель-лаком"},
            {"kind": "addon", "public_name": "Снятие", "quantity": 1},
            {"kind": "addon", "public_name": "Ремонт", "quantity": 3},
        ]
    )

    result = client_repeat_last._snapshot_composition(booking)

    assert result is not None
    assert result.service_name == "Маникюр с гель-лаком"
    assert result.addon_names == ["Снятие", "Ремонт"]
    assert result.addon_quantities == {"ремонт": 3}


def test_pending_client_has_no_repeat_action_and_does_not_query_history():
    class NoQuerySession:
        def scalar(self, _statement):
            raise AssertionError("history must not be queried for an unlinked client")

    preview = client_repeat_last.repeat_last_preview(
        NoQuerySession(),
        _context(client_id=None),
    )

    assert preview.available is False
    assert preview.service_name is None


def test_archived_or_changed_catalog_hides_repeat_action(monkeypatch):
    booking = SimpleNamespace(
        catalog_items_snapshot=[
            {"kind": "base", "public_name": "Старая процедура"},
        ]
    )

    class Session:
        def scalar(self, _statement):
            return booking

    def unavailable(*_args, **_kwargs):
        raise client_repeat_last.SchedulingDomainError(
            "service_not_found",
            status_code=404,
        )

    monkeypatch.setattr(client_repeat_last, "get_active_service", unavailable)

    preview = client_repeat_last.repeat_last_preview(Session(), _context())

    assert preview.available is False


def test_repeat_draft_skips_service_and_addon_lists():
    text = repeat_draft_text(
        {
            "service_name": "Маникюр с гель-лаком",
            "addon_names": ["Снятие", "Ремонт"],
            "addon_quantities": {"ремонт": 2},
        }
    )

    assert text.startswith("Как в прошлый раз")
    assert "Маникюр с гель-лаком" in text
    assert "+ Снятие" in text
    assert "+ Ремонт ×2" in text
    assert text.endswith("Выберите новую дату:")
    assert "Выберите раздел" not in text
    assert "Добавить что-нибудь" not in text


def test_repeat_routes_precede_dynamic_draft_route():
    source = (APP / "api" / "client_booking_drafts.py").read_text(encoding="utf-8")

    preview = source.index('@router.get("/repeat-last"')
    create = source.index('@router.post("/repeat-last"')
    dynamic = source.index('@router.get("/{draft_id}"')

    assert preview < dynamic
    assert create < dynamic
    assert "response_model=ClientRepeatLastPreview" in source


def test_repeat_uses_history_without_new_domain_entity_or_migration():
    source = (APP / "services" / "client_repeat_last.py").read_text(encoding="utf-8")
    models = (APP / "client_models.py").read_text(encoding="utf-8")

    assert "select(Booking)" in source
    assert "catalog_items_snapshot" in source
    assert "BookingStatus.scheduled" in source
    assert "BookingStatus.completed" in source
    assert "class Repeat" not in models
    assert not any(
        path.name.startswith("0023")
        for path in (ROOT / "backend" / "alembic" / "versions").glob("*.py")
    )
