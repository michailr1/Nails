from __future__ import annotations

from typing import Any

from app.client_bot_onboarding import OnboardingDraftPlatformBot
from app.client_bot_runtime_api import RuntimeDraftNailsClientApi

DRAFT_ID = "33333333-3333-4333-8333-333333333333"
BINDING_ID = "11111111-1111-4111-8111-111111111111"


class FakeTelegram:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, **payload: Any) -> Any:
        self.calls.append((method, payload))
        return True


class FakeRuntimeApi(RuntimeDraftNailsClientApi):
    def __init__(self) -> None:
        super().__init__(None, base_url="http://test", api_key="x" * 32)  # type: ignore[arg-type]

    def draft(self, telegram_user_id: int, draft_id: str) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert draft_id == DRAFT_ID
        return {
            "draft_id": DRAFT_ID,
            "master": {
                "binding_id": BINDING_ID,
                "display_name": "Настя",
                "timezone": "Europe/Moscow",
            },
            "service_name": "Маникюр с гель-лаком",
            "starts_at": "2026-08-16T12:45:00+03:00",
            "duration_minutes": 130,
            "price_type": "fixed",
            "price_amount": "2100",
            "currency": "RUB",
            "addon_names": [],
            "addon_quantities": {},
        }

    def submit_draft(self, telegram_user_id: int, draft_id: str) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert draft_id == DRAFT_ID
        return {
            "status": "pending",
            "service_name": "Маникюр с гель-лаком",
            "starts_at": "2026-08-16T09:45:00+00:00",
        }

    def repeat_last_preview(
        self,
        telegram_user_id: int,
        binding_id: str,
    ) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert binding_id == BINDING_ID
        return {"available": False}

    def masters(self, telegram_user_id: int) -> dict[str, Any]:
        assert telegram_user_id == 42
        return {"state": "ready", "masters": []}


def test_production_onboarding_submit_uses_master_local_time() -> None:
    telegram = FakeTelegram()
    bot = OnboardingDraftPlatformBot(telegram, FakeRuntimeApi())

    bot.handle_callback(
        {
            "id": "callback-1",
            "data": f"send:{DRAFT_ID}",
            "from": {"id": 42},
            "message": {"chat": {"id": 99}},
        }
    )

    sent = [payload for method, payload in telegram.calls if method == "sendMessage"]
    assert len(sent) == 1
    text = sent[0]["text"]
    assert "16.08 в 12:45" in text
    assert "09:45" not in text
