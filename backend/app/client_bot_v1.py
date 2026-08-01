from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import httpx

from app.client_bot import BotConfig, TelegramApi
from app.client_bot_onboarding import OnboardingDraftPlatformBot
from app.client_bot_outbox import (
    ClientBotRuntimeState,
    ClientNotificationApi,
    NotificationDrainer,
    OutboxRuntimeConfig,
)
from app.client_bot_runtime_api import (
    ClientDomainRemoteCallError,
    RuntimeDraftNailsClientApi,
)

LOGGER = logging.getLogger("nails.client_bot_v1")


def client_error_message(error: ClientDomainRemoteCallError) -> str:
    messages = {
        "client_booking_draft_expired": (
            "Эта заявка устарела. Начните запись заново через /menu."
        ),
        "client_identity_revoked": (
            "Связь с мастером больше не активна. Откройте актуальную ссылку мастера."
        ),
        "client_booking_slot_stale": (
            "Это время уже заняли. Выберите другое время."
        ),
        "client_pending_request_limit": (
            "У вас уже несколько заявок ждут ответа мастера. "
            "Дождитесь ответа или отмените одну из них."
        ),
        "client_booking_draft_submitted": (
            "Эта заявка уже отправлена мастеру. Откройте /menu для новой записи."
        ),
    }
    return messages.get(
        error.code,
        "Не получилось выполнить действие. Откройте /menu и попробуйте ещё раз.",
    )


def _update_chat_id(update: dict[str, Any]) -> int | None:
    message = update.get("message")
    if not isinstance(message, dict):
        callback = update.get("callback_query")
        if isinstance(callback, dict):
            message = callback.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None
    try:
        chat_id = int(chat.get("id") or 0)
    except (TypeError, ValueError):
        return None
    return chat_id or None


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    config = BotConfig.from_env()
    outbox_config = OutboxRuntimeConfig.from_env()
    state = ClientBotRuntimeState()
    offset = 0
    with httpx.Client() as client:
        telegram = TelegramApi(client, config.telegram_token)
        nails = RuntimeDraftNailsClientApi(
            client,
            base_url=config.client_api_url,
            api_key=config.client_api_key,
        )
        bot = OnboardingDraftPlatformBot(telegram, nails)
        notifications = ClientNotificationApi(client, outbox_config)
        drainer = NotificationDrainer(telegram, notifications, outbox_config, state)
        drain_thread = threading.Thread(
            target=drainer.run,
            name="client-notification-drainer",
            daemon=True,
        )
        drain_thread.start()
        state.write(outbox_config.status_path)
        try:
            while True:
                try:
                    updates = telegram.call(
                        "getUpdates",
                        offset=offset,
                        timeout=config.poll_timeout_seconds,
                        allowed_updates=["message", "callback_query"],
                    )
                    state.mark_poll()
                    state.write(outbox_config.status_path)
                    for update in updates or []:
                        update_id = int(update.get("update_id") or 0)
                        offset = max(offset, update_id + 1)
                        try:
                            bot.handle_update(update)
                        except ClientDomainRemoteCallError as exc:
                            chat_id = _update_chat_id(update)
                            if chat_id is not None:
                                try:
                                    telegram.call(
                                        "sendMessage",
                                        chat_id=chat_id,
                                        text=client_error_message(exc),
                                    )
                                except Exception:
                                    LOGGER.exception(
                                        "CLIENT_BOT_V1_ERROR_REPLY_FAILED update_id=%s",
                                        update_id,
                                    )
                            LOGGER.warning(
                                "CLIENT_BOT_V1_DOMAIN_ERROR update_id=%s code=%s status=%s",
                                update_id,
                                exc.code,
                                exc.status_code,
                            )
                        except Exception:
                            LOGGER.exception(
                                "CLIENT_BOT_V1_UPDATE_FAILED update_id=%s",
                                update_id,
                            )
                except Exception as exc:
                    with state._lock:
                        state.last_error = type(exc).__name__
                    state.write(outbox_config.status_path)
                    LOGGER.exception("CLIENT_BOT_V1_POLL_FAILED")
                    time.sleep(3)
        finally:
            drainer.stop()
            drain_thread.join(timeout=5)


if __name__ == "__main__":
    run()
