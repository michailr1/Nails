from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import httpx

from app.client_bot import (
    BotConfig,
    NailsClientApi,
    PlatformBot,
    TelegramApi,
    parse_start_token,
    telegram_public_name,
)

LOGGER = logging.getLogger("nails.client_bot")


class StickyNailsClientApi(NailsClientApi):
    def masters(self, telegram_user_id: int) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/client/masters",
            telegram_user_id=telegram_user_id,
        )

    def select(
        self,
        telegram_user_id: int,
        binding_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/client/context/select",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
        )


class StickyPlatformBot(PlatformBot):
    _nails: StickyNailsClientApi

    def handle_message(self, message: dict[str, Any]) -> None:
        user = message.get("from") or {}
        telegram_user_id = int(user.get("id") or 0)
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        text = str(message.get("text") or "").strip()
        if telegram_user_id <= 0 or chat_id == 0:
            return

        command = text.split("@", 1)[0].split(" ", 1)[0].lower()
        if command == "/start":
            token = parse_start_token(text)
            payload = (
                self._nails.start(
                    telegram_user_id,
                    token,
                    telegram_public_name(user),
                )
                if token
                else self._nails.context(telegram_user_id)
            )
            self._show_context(chat_id, telegram_user_id, payload)
            return
        if command == "/masters":
            self._show_context(
                chat_id,
                telegram_user_id,
                self._nails.masters(telegram_user_id),
            )
            return
        if command == "/menu":
            self._show_context(
                chat_id,
                telegram_user_id,
                self._nails.context(telegram_user_id),
            )
            return
        super().handle_message(message)

    def handle_callback(self, callback: dict[str, Any]) -> None:
        data = str(callback.get("data") or "")
        if data != "masters" and not data.startswith("master:"):
            super().handle_callback(callback)
            return

        callback_id = str(callback.get("id") or "")
        user = callback.get("from") or {}
        message = callback.get("message") or {}
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        telegram_user_id = int(user.get("id") or 0)
        if callback_id:
            self._telegram.call(
                "answerCallbackQuery",
                callback_query_id=callback_id,
            )
        if telegram_user_id <= 0 or chat_id == 0:
            return

        if data == "masters":
            payload = self._nails.masters(telegram_user_id)
        else:
            binding_id = str(uuid.UUID(data.split(":", 1)[1]))
            payload = self._nails.select(telegram_user_id, binding_id)
        self._show_context(chat_id, telegram_user_id, payload)


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    config = BotConfig.from_env()
    offset = 0
    with httpx.Client() as client:
        telegram = TelegramApi(client, config.telegram_token)
        nails = StickyNailsClientApi(
            client,
            base_url=config.client_api_url,
            api_key=config.client_api_key,
        )
        bot = StickyPlatformBot(telegram, nails)
        while True:
            try:
                updates = telegram.call(
                    "getUpdates",
                    offset=offset,
                    timeout=config.poll_timeout_seconds,
                    allowed_updates=["message", "callback_query"],
                )
                for update in updates or []:
                    update_id = int(update.get("update_id") or 0)
                    offset = max(offset, update_id + 1)
                    try:
                        bot.handle_update(update)
                    except Exception:
                        LOGGER.exception(
                            "CLIENT_BOT_UPDATE_FAILED update_id=%s",
                            update_id,
                        )
            except Exception:
                LOGGER.exception("CLIENT_BOT_POLL_FAILED")
                time.sleep(3)


if __name__ == "__main__":
    run()
