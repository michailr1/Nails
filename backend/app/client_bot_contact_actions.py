from __future__ import annotations

import uuid
from typing import Any

from app.client_bot_my_bookings import booking_request_text, upcoming_booking_requests
from app.client_bot_onboarding import OnboardingDraftPlatformBot

MAX_CLIENT_MESSAGE_LENGTH = 500


def _binding_id(value: str) -> str:
    return str(uuid.UUID(value))


def _telegram_contact(user: dict[str, Any]) -> str:
    telegram_user_id = int(user.get("id") or 0)
    username = str(user.get("username") or "").strip().lstrip("@")
    if username:
        return f"@{username} · Telegram ID {telegram_user_id}"
    return f"Telegram ID {telegram_user_id}"


class ContactAwareOnboardingBot(OnboardingDraftPlatformBot):
    def __init__(self, telegram, nails) -> None:
        super().__init__(telegram, nails)
        self._pending_messages: dict[int, str] = {}
        self._request_bindings: dict[tuple[int, str], str] = {}

    def _menu_keyboard(
        self,
        telegram_user_id: int,
        master: dict[str, Any],
    ) -> dict[str, Any]:
        keyboard = super()._menu_keyboard(telegram_user_id, master)
        binding_id = _binding_id(str(master.get("binding_id") or ""))
        rows = list(keyboard.get("inline_keyboard") or [])
        rows.append(
            [
                {
                    "text": "📁 Мои записи",
                    "callback_data": f"requests:{binding_id}",
                },
                {
                    "text": "💬 Написать мастеру",
                    "callback_data": f"write:{binding_id}",
                },
            ]
        )
        return {"inline_keyboard": rows}

    def _show_requests(
        self,
        chat_id: int,
        telegram_user_id: int,
        binding_id: str,
    ) -> None:
        payload = self._runtime_api().booking_requests(telegram_user_id, binding_id)
        catalog = self._nails.catalog(telegram_user_id, binding_id)
        master = catalog["master"]
        requests = upcoming_booking_requests(payload)
        if not requests:
            self._send(
                chat_id,
                "🗓 Мои записи\n\nБлижайших записей и заявок пока нет.",
                self._menu_keyboard(telegram_user_id, master),
            )
            return
        for item in requests[:8]:
            rows: list[list[dict[str, str]]] = []
            request_id = str(uuid.UUID(str(item.get("id") or "")))
            self._request_bindings[(telegram_user_id, request_id)] = binding_id
            if item.get("status") == "pending":
                rows.append(
                    [
                        {
                            "text": "Отменить заявку",
                            "callback_data": f"cancelreq:{request_id}",
                        }
                    ]
                )
            self._send(
                chat_id,
                booking_request_text(item, master),
                {"inline_keyboard": rows} if rows else None,
            )

    def _start_message(self, chat_id: int, telegram_user_id: int, binding_id: str) -> None:
        self._pending_messages[telegram_user_id] = binding_id
        self._send(
            chat_id,
            "Напишите одно сообщение мастеру — до 500 символов. "
            "Оно не изменит услугу, время или цену заявки.",
            {"force_reply": True, "input_field_placeholder": "Сообщение мастеру"},
        )

    def handle_callback(self, callback: dict[str, Any]) -> None:
        data = str(callback.get("data") or "")
        action, _, rest = data.partition(":")
        user = callback.get("from") or {}
        message = callback.get("message") or {}
        telegram_user_id = int(user.get("id") or 0)
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        callback_id = str(callback.get("id") or "")

        if action not in {"requests", "cancelreq", "write", "help"}:
            return super().handle_callback(callback)
        if callback_id:
            self._telegram.call("answerCallbackQuery", callback_query_id=callback_id)
        if telegram_user_id <= 0 or chat_id == 0:
            return

        if action == "requests":
            self._show_requests(chat_id, telegram_user_id, _binding_id(rest))
            return
        if action == "cancelreq":
            request_id = str(uuid.UUID(rest))
            binding_id = self._request_bindings.get((telegram_user_id, request_id))
            if binding_id is None:
                self._send(chat_id, "Откройте «Мои записи» и попробуйте ещё раз.")
                return
            self._runtime_api().cancel_booking_request(
                telegram_user_id,
                binding_id,
                request_id,
            )
            self._send(chat_id, "Заявка отменена.")
            return
        if action == "write":
            self._start_message(chat_id, telegram_user_id, _binding_id(rest))
            return

        binding_id = _binding_id(rest)
        text = (
            "Клиентка не уверена, какую процедуру выбрать, и просит подсказать.\n"
            f"Контакт: {_telegram_contact(user)}"
        )
        self._runtime_api().contact_forward(telegram_user_id, binding_id, text)
        self._send(
            chat_id,
            "Передала мастеру просьбу помочь с выбором. "
            "Можно также отправить ей одно сообщение.",
            {
                "inline_keyboard": [
                    [
                        {
                            "text": "💬 Написать мастеру",
                            "callback_data": f"write:{binding_id}",
                        }
                    ]
                ]
            },
        )

    def handle_message(self, message: dict[str, Any]) -> None:
        user = message.get("from") or {}
        telegram_user_id = int(user.get("id") or 0)
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        text = str(message.get("text") or "").strip()
        binding_id = self._pending_messages.get(telegram_user_id)
        if binding_id and text and not text.startswith("/"):
            if len(text) > MAX_CLIENT_MESSAGE_LENGTH:
                self._send(chat_id, "Сообщение слишком длинное. Максимум 500 символов.")
                return
            self._pending_messages.pop(telegram_user_id, None)
            forwarded = (
                "Сообщение клиентки:\n"
                f"{text}\n\n"
                f"Контакт: {_telegram_contact(user)}"
            )
            self._runtime_api().contact_forward(
                telegram_user_id,
                binding_id,
                forwarded,
            )
            self._send(
                chat_id,
                "Сообщение передано мастеру. Оно не меняет параметры заявки.",
            )
            return
        super().handle_message(message)
