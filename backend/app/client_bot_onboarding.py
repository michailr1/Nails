# ruff: noqa: I001
from __future__ import annotations

import uuid
from typing import Any

from app.client_bot import master_picker_keyboard
from app.client_bot_booking_flow import (
    DraftPlatformBot,
    draft_date_picker_keyboard,
    draft_submitted_text,
)
from app.client_bot_catalog_sections import (
    catalog_categories,
    category_page,
    category_picker_keyboard,
    parse_category_callback,
)
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
    repeat_available: bool = False,
) -> dict[str, Any]:
    binding_id = str(uuid.UUID(str(master.get("binding_id") or "")))
    rows: list[list[dict[str, str]]] = []
    if repeat_available:
        rows.append(
            [
                {
                    "text": "🔁 Как в прошлый раз",
                    "callback_data": f"repeat:{binding_id}",
                }
            ]
        )
    rows.append(
        [
            {"text": "💅 Прайс", "callback_data": f"price:{binding_id}"},
            {"text": "📅 Записаться", "callback_data": f"book:{binding_id}"},
        ]
    )
    if show_masters:
        rows.append([{"text": "👩 Ваши мастера", "callback_data": "masters"}])
    return {"inline_keyboard": rows}


def repeat_draft_text(draft: dict[str, Any]) -> str:
    lines = ["Как в прошлый раз", "", str(draft.get("service_name") or "Процедура")]
    quantities = draft.get("addon_quantities") or {}
    for name in draft.get("addon_names") or []:
        quantity = int(quantities.get(str(name).casefold(), 1))
        suffix = f" ×{quantity}" if quantity > 1 else ""
        lines.append(f"+ {name}{suffix}")
    lines.extend(["", "Выберите новую дату:"])
    return "\n".join(lines)


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
        binding_id = str(uuid.UUID(str(master.get("binding_id") or "")))
        repeat = self._runtime_api().repeat_last_preview(
            telegram_user_id,
            binding_id,
        )
        return client_menu_keyboard(
            master,
            show_masters=self._has_multiple_masters(telegram_user_id),
            repeat_available=repeat.get("available") is True,
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

    def _show_catalog_sections(
        self,
        chat_id: int,
        telegram_user_id: int,
        binding_id: str,
        *,
        mode: str,
    ) -> None:
        catalog = self._nails.catalog(telegram_user_id, binding_id)
        categories = catalog_categories(catalog, mode=mode)  # type: ignore[arg-type]
        if not categories:
            self._send(
                chat_id,
                "Прайс пока пуст." if mode == "price" else "Запись пока недоступна.",
                self._menu_keyboard(telegram_user_id, catalog["master"]),
            )
            return
        prompt = "Выберите раздел прайса:" if mode == "price" else "Что хотите сделать?"
        self._send(
            chat_id,
            prompt,
            category_picker_keyboard(catalog, mode=mode),  # type: ignore[arg-type]
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
        action, _, rest = data.partition(":")
        handled = {
            "masters",
            "price",
            "book",
            "cat",
            "pcat",
            "help",
            "repeat",
            "send",
        }
        if data != "masters" and action not in handled:
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

        if action in {"price", "book"}:
            binding_id = str(uuid.UUID(rest))
            self._show_catalog_sections(
                chat_id,
                telegram_user_id,
                binding_id,
                mode="price" if action == "price" else "book",
            )
            return

        if action == "repeat":
            binding_id = str(uuid.UUID(rest))
            draft = self._runtime_api().create_repeat_last_draft(
                telegram_user_id,
                binding_id,
            )
            self._send(
                chat_id,
                repeat_draft_text(draft),
                draft_date_picker_keyboard(str(draft["draft_id"])),
            )
            return

        if action in {"cat", "pcat"}:
            binding_id, category_index, page = parse_category_callback(rest)
            catalog = self._nails.catalog(telegram_user_id, binding_id)
            text, keyboard = category_page(
                catalog,
                category_index=category_index,
                page=page,
                mode="price" if action == "pcat" else "book",
            )
            self._send(chat_id, text, keyboard)
            return

        if action == "help":
            binding_id = str(uuid.UUID(rest))
            catalog = self._nails.catalog(telegram_user_id, binding_id)
            self._runtime_api().contact_forward(
                telegram_user_id,
                binding_id,
                "Клиентка не уверена, какую процедуру выбрать, и просит подсказать.",
            )
            self._send(
                chat_id,
                "Передала мастеру, что вам нужна помощь с выбором. Она ответит в Telegram.",
                self._menu_keyboard(telegram_user_id, catalog["master"]),
            )
            return

        draft_id = str(uuid.UUID(rest))
        api = self._draft_api()
        draft = api.draft(telegram_user_id, draft_id)
        result = api.submit_draft(telegram_user_id, draft_id)
        if result.get("status") != "pending":
            raise ValueError("unexpected booking request status")
        self._send(
            chat_id,
            draft_submitted_text(draft, result),
            self._menu_keyboard(telegram_user_id, draft["master"]),
        )
