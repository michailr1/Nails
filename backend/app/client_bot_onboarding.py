from __future__ import annotations

import uuid
from typing import Any

from app.client_bot import _parse_slot, format_catalog, master_picker_keyboard
from app.client_bot_booking_flow import DraftPlatformBot
from app.client_bot_runtime_api import RuntimeDraftNailsClientApi


ONBOARDING_TEXT = (
    "👋 Вы подключились к записи мастера {master}.\n\n"
    "Здесь можно посмотреть прайс, выбрать процедуру и свободное время, "
    "а затем отправить заявку. Мастер подтвердит запись отдельным сообщением — "
    "до подтверждения время ещё не забронировано."
)
CONTACT_PROMPT = (
    "Чтобы мастер мог узнать вас и связаться по записи, поделитесь номером "
    "телефона кнопкой ниже. Номер увидит только ваш мастер."
)


def contact_request_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [
            [
                {
                    "text": "📱 Поделиться номером",
                    "request_contact": True,
                }
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True,
        "input_field_placeholder": "Нажмите кнопку ниже",
    }


def client_menu_keyboard(
    master: dict[str, Any],
    *,
    show_masters: bool,
) -> dict[str, Any]:
    binding_id = str(uuid.UUID(str(master.get("binding_id") or "")))
    rows: list[list[dict[str, str]]] = [
        [
            {"text": "💅 Прайс", "callback_data": f"price:{binding_id}"},
            {"text": "📅 Записаться", "callback_data": f"book:{binding_id}"},
        ]
    ]
    if show_masters:
        rows.append([{"text": "👩 Ваши мастера", "callback_data": "masters"}])
    return {"inline_keyboard": rows}


class OnboardingDraftPlatformBot(DraftPlatformBot):
    def _runtime_api(self) -> RuntimeDraftNailsClientApi:
        if not isinstance(self._nails, RuntimeDraftNailsClientApi):
            raise TypeError("OnboardingDraftPlatformBot requires RuntimeDraftNailsClientApi")
        return self._nails

    def _has_multiple_masters(self, telegram_user_id: int) -> bool:
        payload = self._runtime_api().masters(telegram_user_id)
        return payload.get("state") == "choose_master" and len(
            payload.get("masters") or []
        ) > 1

    def _menu_keyboard(
        self,
        telegram_user_id: int,
        master: dict[str, Any],
    ) -> dict[str, Any]:
        return client_menu_keyboard(
            master,
            show_masters=self._has_multiple_masters(telegram_user_id),
        )

    def _show_context(
        self,
        chat_id: int,
        telegram_user_id: int,
        payload: dict[str, Any],
    ) -> None:
        state = payload.get("state")
        master = payload.get("master")
        if state == "ready" and isinstance(master, dict):
            display_name = str(master.get("display_name") or "мастера").strip()
            self._send(
                chat_id,
                ONBOARDING_TEXT.format(master=display_name),
                self._menu_keyboard(telegram_user_id, master),
            )
            if payload.get("contact_required") is True:
                self._send(chat_id, CONTACT_PROMPT, contact_request_keyboard())
            return
        if state == "choose_master":
            self._send(
                chat_id,
                "Выберите мастера, к которому хотите записаться.",
                master_picker_keyboard(payload.get("masters") or []),
            )
            return
        self._send(
            chat_id,
            str(payload.get("message") or "Запись сейчас недоступна."),
        )

    def _show_master(
        self,
        chat_id: int,
        telegram_user_id: int,
        binding_id: str,
    ) -> None:
        catalog = self._nails.catalog(telegram_user_id, binding_id)
        master = catalog["master"]
        display_name = str(master.get("display_name") or "Мастер")
        self._send(
            chat_id,
            f"Вы записываетесь к {display_name}.",
            self._menu_keyboard(telegram_user_id, master),
        )

    def _handle_contact(
        self,
        message: dict[str, Any],
        *,
        telegram_user_id: int,
        chat_id: int,
    ) -> bool:
        contact = message.get("contact")
        if not isinstance(contact, dict):
            return False
        context = self._nails.context(telegram_user_id)
        master = context.get("master")
        if context.get("state") != "ready" or not isinstance(master, dict):
            self._send(chat_id, "Сначала откройте ссылку вашего мастера для записи.")
            return True
        binding_id = str(uuid.UUID(str(master.get("binding_id") or "")))
        self._runtime_api().confirmed_contact(
            telegram_user_id,
            binding_id,
            contact_user_id=int(contact.get("user_id") or 0),
            phone_number=str(contact.get("phone_number") or ""),
        )
        self._send(
            chat_id,
            "Спасибо, номер сохранён для этого мастера.",
            {"remove_keyboard": True},
        )
        self._send(
            chat_id,
            "Теперь можно посмотреть прайс или выбрать время для записи.",
            self._menu_keyboard(telegram_user_id, master),
        )
        return True

    def handle_message(self, message: dict[str, Any]) -> None:
        user = message.get("from") or {}
        telegram_user_id = int(user.get("id") or 0)
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        if telegram_user_id > 0 and chat_id != 0 and self._handle_contact(
            message,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
        ):
            return
        super().handle_message(message)

    def handle_callback(self, callback: dict[str, Any]) -> None:
        data = str(callback.get("data") or "")
        if data != "masters" and not data.startswith(("price:", "send:")):
            return super().handle_callback(callback)

        callback_id = str(callback.get("id") or "")
        user = callback.get("from") or {}
        message = callback.get("message") or {}
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        telegram_user_id = int(user.get("id") or 0)
        if callback_id:
            self._telegram.call("answerCallbackQuery", callback_query_id=callback_id)
        if telegram_user_id <= 0 or chat_id == 0:
            return

        if data == "masters":
            self._show_context(
                chat_id,
                telegram_user_id,
                self._runtime_api().masters(telegram_user_id),
            )
            return

        action, _, rest = data.partition(":")
        if action == "price":
            binding_id = str(uuid.UUID(rest))
            catalog = self._nails.catalog(telegram_user_id, binding_id)
            self._send(
                chat_id,
                format_catalog(catalog),
                self._menu_keyboard(telegram_user_id, catalog["master"]),
            )
            return

        draft_id = str(uuid.UUID(rest))
        api = self._draft_api()
        draft = api.draft(telegram_user_id, draft_id)
        result = api.submit_draft(telegram_user_id, draft_id)
        if result.get("status") != "pending":
            raise ValueError("unexpected booking request status")
        parsed = _parse_slot(result["starts_at"])
        self._send(
            chat_id,
            "✅ Заявка отправлена\n"
            f"{result.get('service_name')}\n"
            f"{parsed:%d.%m} в {parsed:%H:%M}\n\n"
            "Мастер подтвердит запись. Пока время не забронировано.",
            self._menu_keyboard(telegram_user_id, draft["master"]),
        )
