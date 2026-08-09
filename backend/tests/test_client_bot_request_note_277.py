from __future__ import annotations

from datetime import date
from typing import Any

from app.client_bot_contact_actions import ContactAwareOnboardingBot
from app.client_bot_runtime_api import RuntimeDraftNailsClientApi

DRAFT_ID = "33333333-3333-4333-8333-333333333333"
BINDING_ID = "11111111-1111-4111-8111-111111111111"
COMPACT = "202608301300"
STARTS_AT = "2026-08-30T13:00:00+03:00"


class FakeTelegram:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, **payload: Any) -> Any:
        self.calls.append((method, payload))
        return True


class FakeRuntimeApi(RuntimeDraftNailsClientApi):
    def __init__(self, *, stale: bool = False) -> None:
        super().__init__(None, base_url="http://test", api_key="x" * 32)  # type: ignore[arg-type]
        self.stale = stale
        self.saved_notes: list[str | None] = []

    def draft_slots(
        self,
        telegram_user_id: int,
        draft_id: str,
        day: date,
    ) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert draft_id == DRAFT_ID
        assert day == date(2026, 8, 30)
        return {
            "starts_at": [] if self.stale else [STARTS_AT],
            "draft": self._summary(starts_at=None),
        }

    def select_draft_slot(
        self,
        telegram_user_id: int,
        draft_id: str,
        starts_at: str,
    ) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert draft_id == DRAFT_ID
        assert starts_at == STARTS_AT
        return self._summary(starts_at=STARTS_AT)

    def draft(self, telegram_user_id: int, draft_id: str) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert draft_id == DRAFT_ID
        return self._summary(starts_at=STARTS_AT)

    def update_draft_note(
        self,
        telegram_user_id: int,
        draft_id: str,
        note: str | None,
    ) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert draft_id == DRAFT_ID
        self.saved_notes.append(note)
        return self._summary(starts_at=STARTS_AT, note=note)

    @staticmethod
    def _summary(
        *,
        starts_at: str | None,
        note: str | None = None,
    ) -> dict[str, Any]:
        return {
            "draft_id": DRAFT_ID,
            "master": {
                "binding_id": BINDING_ID,
                "display_name": "Настя",
                "timezone": "Europe/Moscow",
            },
            "service_name": "Маникюр",
            "addon_names": [],
            "addon_quantities": {},
            "note": note,
            "starts_at": starts_at,
            "duration_minutes": 60,
            "price_type": "fixed",
            "price_amount": "2500.00",
            "price_min_amount": None,
            "price_max_amount": None,
            "price_unit": None,
            "currency": "RUB",
            "addons": [],
        }


def _callback(data: str) -> dict[str, Any]:
    return {
        "id": "callback-1",
        "data": data,
        "from": {"id": 42},
        "message": {"chat": {"id": 99}},
    }


def _message(text: str) -> dict[str, Any]:
    return {
        "from": {"id": 42},
        "chat": {"id": 99},
        "text": text,
    }


def _sent(telegram: FakeTelegram) -> list[dict[str, Any]]:
    return [payload for method, payload in telegram.calls if method == "sendMessage"]


def _callbacks(message: dict[str, Any]) -> list[str]:
    return [
        button["callback_data"]
        for row in (message.get("reply_markup") or {}).get("inline_keyboard", [])
        for button in row
    ]


def test_valid_slot_summary_offers_optional_note_without_extra_message() -> None:
    telegram = FakeTelegram()
    bot = ContactAwareOnboardingBot(telegram, FakeRuntimeApi())

    bot.handle_callback(_callback(f"t:{DRAFT_ID}:{COMPACT}"))

    sent = _sent(telegram)
    assert len(sent) == 1
    assert "Проверьте заявку" in sent[0]["text"]
    callbacks = _callbacks(sent[0])
    assert f"send:{DRAFT_ID}" in callbacks
    assert f"note:{DRAFT_ID}" in callbacks


def test_stale_slot_does_not_offer_note_action() -> None:
    telegram = FakeTelegram()
    bot = ContactAwareOnboardingBot(telegram, FakeRuntimeApi(stale=True))

    bot.handle_callback(_callback(f"t:{DRAFT_ID}:{COMPACT}"))

    sent = _sent(telegram)
    assert len(sent) == 1
    assert "Это время уже заняли" in sent[0]["text"]
    assert not any(value.startswith("note:") for value in _callbacks(sent[0]))


def test_note_is_one_shot_and_returns_to_same_sendable_summary() -> None:
    telegram = FakeTelegram()
    api = FakeRuntimeApi()
    bot = ContactAwareOnboardingBot(telegram, api)

    bot.handle_callback(_callback(f"note:{DRAFT_ID}"))
    prompt = _sent(telegram)[-1]
    assert "до 300 символов" in prompt["text"]

    bot.handle_message(_message("Без дизайна"))

    assert api.saved_notes == ["Без дизайна"]
    sent = _sent(telegram)
    summary = sent[-1]
    assert "Заметка сохранена" in summary["text"]
    callbacks = _callbacks(summary)
    assert f"send:{DRAFT_ID}" in callbacks
    assert f"note:{DRAFT_ID}" in callbacks
