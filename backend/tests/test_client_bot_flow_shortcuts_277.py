from __future__ import annotations

from typing import Any

from app.client_bot_onboarding import OnboardingDraftPlatformBot
from app.client_bot_runtime_api import RuntimeDraftNailsClientApi

BINDING_ID = "11111111-1111-4111-8111-111111111111"
DRAFT_ID = "33333333-3333-4333-8333-333333333333"


class FakeTelegram:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, **payload: Any) -> Any:
        self.calls.append((method, payload))
        return True


class FakeRuntimeApi(RuntimeDraftNailsClientApi):
    def __init__(self) -> None:
        super().__init__(None, base_url="http://test", api_key="x" * 32)  # type: ignore[arg-type]

    def catalog(self, telegram_user_id: int, binding_id: str) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert binding_id == BINDING_ID
        return {
            "master": {
                "binding_id": BINDING_ID,
                "display_name": "Настя",
                "timezone": "Europe/Moscow",
            },
            "services": [
                {
                    "kind": "base",
                    "public_name": "Маникюр с гель-лаком",
                    "category": "Маникюр",
                }
            ],
        }

    def create_draft(
        self,
        telegram_user_id: int,
        binding_id: str,
        service_name: str,
    ) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert binding_id == BINDING_ID
        assert service_name == "Маникюр с гель-лаком"
        return {
            "draft_id": DRAFT_ID,
            "master": {
                "binding_id": BINDING_ID,
                "display_name": "Настя",
                "timezone": "Europe/Moscow",
            },
            "service_name": service_name,
            "addons": [
                {
                    "public_name": "Снятие",
                    "quantity_supported": False,
                }
            ],
            "addon_names": [],
            "addon_quantities": {},
        }

    def create_repeat_last_draft(
        self,
        telegram_user_id: int,
        binding_id: str,
    ) -> dict[str, Any]:
        assert telegram_user_id == 42
        assert binding_id == BINDING_ID
        return {
            "draft_id": DRAFT_ID,
            "master": {
                "binding_id": BINDING_ID,
                "display_name": "Настя",
                "timezone": "Europe/Moscow",
            },
            "service_name": "Маникюр с гель-лаком",
            "addon_names": ["Снятие"],
            "addon_quantities": {"снятие": 1},
        }


def _callback(data: str) -> dict[str, Any]:
    return {
        "id": "callback-1",
        "data": data,
        "from": {"id": 42},
        "message": {"chat": {"id": 99}},
    }


def _sent_messages(telegram: FakeTelegram) -> list[dict[str, Any]]:
    return [payload for method, payload in telegram.calls if method == "sendMessage"]


def test_service_choice_skips_mandatory_addon_step() -> None:
    telegram = FakeTelegram()
    bot = OnboardingDraftPlatformBot(telegram, FakeRuntimeApi())

    bot.handle_callback(_callback(f"svc:{BINDING_ID}:0"))

    sent = _sent_messages(telegram)
    assert len(sent) == 1
    assert "Выберите дату" in sent[0]["text"]
    assert "Добавить что-нибудь?" not in sent[0]["text"]
    callbacks = [
        button["callback_data"]
        for row in sent[0]["reply_markup"]["inline_keyboard"]
        for button in row
    ]
    assert any(value.startswith(f"d:{DRAFT_ID}:") for value in callbacks)
    assert not any(value.startswith(f"a:{DRAFT_ID}:") for value in callbacks)


def test_repeat_last_opens_owner_local_date_picker() -> None:
    telegram = FakeTelegram()
    bot = OnboardingDraftPlatformBot(telegram, FakeRuntimeApi())

    bot.handle_callback(_callback(f"repeat:{BINDING_ID}"))

    sent = _sent_messages(telegram)
    assert len(sent) == 1
    assert "Как в прошлый раз" in sent[0]["text"]
    assert "Выберите новую дату" in sent[0]["text"]
    callbacks = [
        button["callback_data"]
        for row in sent[0]["reply_markup"]["inline_keyboard"]
        for button in row
    ]
    assert any(value.startswith(f"d:{DRAFT_ID}:") for value in callbacks)
