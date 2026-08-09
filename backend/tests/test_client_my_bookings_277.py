from __future__ import annotations

from typing import Any

from app.client_bot_contact_actions import ContactAwareOnboardingBot
from app.client_bot_runtime_api import RuntimeDraftNailsClientApi

BINDING_ID = "11111111-1111-4111-8111-111111111111"
PENDING_ID = "22222222-2222-4222-8222-222222222222"
APPROVED_ID = "33333333-3333-4333-8333-333333333333"
CANCELLED_ID = "44444444-4444-4444-8444-444444444444"


class FakeTelegram:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, **payload: Any) -> Any:
        self.calls.append((method, payload))
        return True


class FakeRuntimeApi(RuntimeDraftNailsClientApi):
    def __init__(self) -> None:
        super().__init__(None, base_url="http://test", api_key="x" * 32)  # type: ignore[arg-type]

    def booking_requests(self, telegram_user_id: int, binding_id: str) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert binding_id == BINDING_ID
        return {
            "requests": [
                {
                    "id": PENDING_ID,
                    "status": "pending",
                    "service_name": "Педикюр",
                    "addon_names": [],
                    "addon_quantities": {},
                    "starts_at": "2099-08-17T09:00:00+00:00",
                },
                {
                    "id": CANCELLED_ID,
                    "status": "cancelled",
                    "service_name": "Не показывать",
                    "addon_names": [],
                    "addon_quantities": {},
                    "starts_at": "2099-08-16T08:00:00+00:00",
                },
                {
                    "id": APPROVED_ID,
                    "status": "approved",
                    "service_name": "Маникюр",
                    "addon_names": ["Снятие"],
                    "addon_quantities": {"снятие": 1},
                    "starts_at": "2099-08-16T09:45:00+00:00",
                },
            ]
        }

    def catalog(self, telegram_user_id: int, binding_id: str) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert binding_id == BINDING_ID
        return {
            "master": {
                "binding_id": BINDING_ID,
                "display_name": "Настя",
                "timezone": "Europe/Moscow",
            },
            "services": [],
        }


def test_my_bookings_shows_only_upcoming_owner_local_requests() -> None:
    telegram = FakeTelegram()
    bot = ContactAwareOnboardingBot(telegram, FakeRuntimeApi())

    bot.handle_callback(
        {
            "id": "callback-1",
            "data": f"requests:{BINDING_ID}",
            "from": {"id": 42},
            "message": {"chat": {"id": 99}},
        }
    )

    sent = [payload for method, payload in telegram.calls if method == "sendMessage"]
    assert len(sent) == 2

    approved = sent[0]
    pending = sent[1]

    assert "16.08 в 12:45 — Маникюр" in approved["text"]
    assert "+ Снятие" in approved["text"]
    assert "✅ подтверждена" in approved["text"]
    assert "09:45" not in approved["text"]
    assert "reply_markup" not in approved

    assert "17.08 в 12:00 — Педикюр" in pending["text"]
    assert "⏳ ждёт подтверждения" in pending["text"]
    callbacks = [
        button["callback_data"]
        for row in pending["reply_markup"]["inline_keyboard"]
        for button in row
    ]
    assert callbacks == [f"cancelreq:{PENDING_ID}"]

    assert all("Не показывать" not in message["text"] for message in sent)
