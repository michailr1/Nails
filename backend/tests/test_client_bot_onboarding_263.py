from __future__ import annotations

from typing import Any

import httpx

from app.client_bot_onboarding import (
    CONTACT_PROMPT,
    ONBOARDING_TEXT,
    OnboardingDraftPlatformBot,
    client_menu_keyboard,
    contact_request_keyboard,
)
from app.client_bot_runtime_api import RuntimeDraftNailsClientApi

BINDING_A = "11111111-1111-4111-8111-111111111111"
BINDING_B = "22222222-2222-4222-8222-222222222222"


def _master(binding_id: str, name: str) -> dict[str, Any]:
    return {
        "binding_id": binding_id,
        "display_name": name,
        "public_contact": None,
    }


def test_single_master_menu_has_no_master_picker_action():
    keyboard = client_menu_keyboard(
        _master(BINDING_A, "Мария"),
        show_masters=False,
    )
    callbacks = [
        button["callback_data"]
        for row in keyboard["inline_keyboard"]
        for button in row
    ]
    assert callbacks == [f"price:{BINDING_A}", f"book:{BINDING_A}"]
    assert "masters" not in callbacks


def test_multiple_master_menu_exposes_picker_without_owner_ids():
    keyboard = client_menu_keyboard(
        _master(BINDING_A, "Мария"),
        show_masters=True,
    )
    callbacks = [
        button["callback_data"]
        for row in keyboard["inline_keyboard"]
        for button in row
    ]
    assert callbacks == [f"price:{BINDING_A}", f"book:{BINDING_A}", "masters"]
    assert "owner_user_id" not in str(keyboard)
    assert "telegram_user_id" not in str(keyboard)


def test_contact_keyboard_uses_native_telegram_contact_request():
    keyboard = contact_request_keyboard()
    button = keyboard["keyboard"][0][0]
    assert button == {
        "text": "📱 Поделиться номером",
        "request_contact": True,
    }
    assert keyboard["one_time_keyboard"] is True


class _FakeTelegram:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, **payload: Any) -> None:
        self.calls.append((method, payload))


class _FakeRuntimeApi(RuntimeDraftNailsClientApi):
    def __init__(self, *, multiple: bool = False) -> None:
        self.multiple = multiple
        self.confirmed: list[dict[str, Any]] = []

    def masters(self, telegram_user_id: int) -> dict[str, Any]:
        assert telegram_user_id == 900001
        if self.multiple:
            return {
                "state": "choose_master",
                "masters": [
                    _master(BINDING_A, "Мария"),
                    _master(BINDING_B, "Анна"),
                ],
            }
        return {
            "state": "ready",
            "master": _master(BINDING_A, "Мария"),
            "masters": [],
        }

    def context(self, telegram_user_id: int) -> dict[str, Any]:
        assert telegram_user_id == 900001
        return {
            "state": "ready",
            "master": _master(BINDING_A, "Мария"),
        }

    def confirmed_contact(
        self,
        telegram_user_id: int,
        binding_id: str,
        *,
        contact_user_id: int,
        phone_number: str,
    ) -> dict[str, Any]:
        self.confirmed.append(
            {
                "telegram_user_id": telegram_user_id,
                "binding_id": binding_id,
                "contact_user_id": contact_user_id,
                "phone_number": phone_number,
            }
        )
        return {"confirmed": True, "linked": False}


def _sent(telegram: _FakeTelegram) -> list[dict[str, Any]]:
    return [payload for method, payload in telegram.calls if method == "sendMessage"]


def test_fresh_start_explains_flow_and_requests_contact():
    telegram = _FakeTelegram()
    bot = OnboardingDraftPlatformBot(telegram, _FakeRuntimeApi())

    bot._show_context(
        900001,
        900001,
        {
            "state": "ready",
            "master": _master(BINDING_A, "Мария"),
            "contact_required": True,
        },
    )

    sent = _sent(telegram)
    assert len(sent) == 2
    assert ONBOARDING_TEXT.format(master="Мария") == sent[0]["text"]
    assert "Мастер подтвердит запись" in sent[0]["text"]
    assert "masters" not in str(sent[0]["reply_markup"])
    assert sent[1]["text"] == CONTACT_PROMPT
    assert sent[1]["reply_markup"]["keyboard"][0][0]["request_contact"] is True


def test_known_contact_is_not_requested_again():
    telegram = _FakeTelegram()
    bot = OnboardingDraftPlatformBot(telegram, _FakeRuntimeApi())

    bot._show_context(
        900001,
        900001,
        {
            "state": "ready",
            "master": _master(BINDING_A, "Мария"),
            "contact_required": False,
        },
    )

    sent = _sent(telegram)
    assert len(sent) == 1
    assert "request_contact" not in str(sent)


def test_shared_own_contact_is_confirmed_in_binding_scope_and_keyboard_removed():
    telegram = _FakeTelegram()
    api = _FakeRuntimeApi()
    bot = OnboardingDraftPlatformBot(telegram, api)

    bot.handle_message(
        {
            "from": {"id": 900001, "first_name": "Ирина"},
            "chat": {"id": 900001},
            "contact": {"user_id": 900001, "phone_number": "+79991112233"},
        }
    )

    assert api.confirmed == [
        {
            "telegram_user_id": 900001,
            "binding_id": BINDING_A,
            "contact_user_id": 900001,
            "phone_number": "+79991112233",
        }
    ]
    sent = _sent(telegram)
    assert sent[0]["reply_markup"] == {"remove_keyboard": True}
    assert "masters" not in str(sent[1]["reply_markup"])


def test_runtime_api_posts_confirmed_contact_without_owner_override():
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["binding"] = request.headers.get("X-Client-Binding-ID")
        seen["telegram"] = request.headers.get("X-Telegram-User-ID")
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"confirmed": True, "linked": False})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        api = RuntimeDraftNailsClientApi(
            http,
            base_url="http://nails-api",
            api_key="c" * 64,
        )
        result = api.confirmed_contact(
            900001,
            BINDING_A,
            contact_user_id=900001,
            phone_number="+79991112233",
        )

    assert result["confirmed"] is True
    assert seen["url"] == (
        "http://nails-api/api/v1/client/linking/confirmed-contact"
    )
    assert seen["binding"] == BINDING_A
    assert seen["telegram"] == "900001"
    assert '"contact_user_id":900001' in seen["body"]
    assert '"owner_user_id"' not in seen["body"]
