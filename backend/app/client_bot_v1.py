from __future__ import annotations

import logging
import os
import threading
import time

import httpx

from app.client_bot import BotConfig, TelegramApi
from app.client_bot_booking_flow import DraftNailsClientApi, DraftPlatformBot
from app.client_bot_outbox import (
    ClientBotRuntimeState,
    ClientNotificationApi,
    NotificationDrainer,
    OutboxRuntimeConfig,
)

LOGGER = logging.getLogger("nails.client_bot_v1")


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    config = BotConfig.from_env()
    outbox_config = OutboxRuntimeConfig.from_env()
    state = ClientBotRuntimeState()
    offset = 0
    with httpx.Client() as client:
        telegram = TelegramApi(client, config.telegram_token)
        nails = DraftNailsClientApi(
            client,
            base_url=config.client_api_url,
            api_key=config.client_api_key,
        )
        bot = DraftPlatformBot(telegram, nails)
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
