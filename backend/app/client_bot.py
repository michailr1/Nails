from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

LOGGER = logging.getLogger("nails.client_bot")


class ClientBotConfigError(RuntimeError):
    pass


class RemoteCallError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BotConfig:
    telegram_token: str
    client_api_key: str
    client_api_url: str
    poll_timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> BotConfig:
        token = os.getenv("CLIENT_TELEGRAM_BOT_TOKEN", "").strip()
        api_key = os.getenv("CLIENT_INTERNAL_API_KEY", "").strip()
        api_url = os.getenv(
            "NAILS_CLIENT_API_URL",
            "http://nails-api:8000",
        ).rstrip("/")
        if not token:
            raise ClientBotConfigError("CLIENT_TELEGRAM_BOT_TOKEN is required")
        if len(api_key) < 32:
            raise ClientBotConfigError(
                "CLIENT_INTERNAL_API_KEY must contain at least 32 characters"
            )
        if not api_url.startswith(("http://", "https://")):
            raise ClientBotConfigError("NAILS_CLIENT_API_URL must be an HTTP(S) URL")
        try:
            timeout = int(os.getenv("CLIENT_TELEGRAM_POLL_TIMEOUT_SECONDS", "30"))
        except ValueError as exc:
            raise ClientBotConfigError(
                "CLIENT_TELEGRAM_POLL_TIMEOUT_SECONDS must be an integer"
            ) from exc
        if not 5 <= timeout <= 50:
            raise ClientBotConfigError(
                "CLIENT_TELEGRAM_POLL_TIMEOUT_SECONDS must be between 5 and 50"
            )
        return cls(
            telegram_token=token,
            client_api_key=api_key,
            client_api_url=api_url,
            poll_timeout_seconds=timeout,
        )


def parse_start_token(text: str) -> str | None:
    command, _, argument = text.strip().partition(" ")
    if command.split("@", 1)[0].lower() != "/start":
        return None
    token = argument.strip()
    return token or None


def telegram_public_name(user: dict[str, Any]) -> str:
    parts = [
        str(user.get(key, "")).strip()
        for key in ("first_name", "last_name")
    ]
    display = " ".join(part for part in parts if part)
    if display:
        return display[:160]
    username = str(user.get("username", "")).strip()
    if username:
        return f"@{username}"[:160]
    return "Клиентка"


def _plain_message(text: str) -> str:
    return text.replace("**", "")


def _binding_id(master: dict[str, Any]) -> str:
    value = str(master.get("binding_id", ""))
    uuid.UUID(value)
    return value


def master_picker_keyboard(
    masters: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for master in masters:
        binding_id = _binding_id(master)
        display_name = str(master.get("display_name", "")).strip() or "Мастер"
        rows.append(
            [
                {
                    "text": display_name[:48],
                    "callback_data": f"master:{binding_id}",
                }
            ]
        )
    return {"inline_keyboard": rows}


def master_menu_keyboard(master: dict[str, Any]) -> dict[str, Any]:
    binding_id = _binding_id(master)
    return {
        "inline_keyboard": [
            [
                {"text": "💅 Прайс", "callback_data": f"price:{binding_id}"},
                {"text": "📅 Записаться", "callback_data": f"book:{binding_id}"},
            ],
            [{"text": "👩 Ваши мастера", "callback_data": "masters"}],
        ]
    }


def _amount(value: Any) -> str | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    if amount == amount.to_integral():
        return f"{int(amount):,}".replace(",", " ")
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def format_service_price(service: dict[str, Any]) -> str:
    price_type = service.get("price_type")
    currency = str(service.get("currency") or "RUB")
    suffix = " ₽" if currency == "RUB" else f" {currency}"
    if price_type == "fixed":
        amount = _amount(service.get("price_amount"))
        return f"{amount}{suffix}" if amount is not None else "цена уточняется"
    if price_type == "range":
        low = _amount(service.get("price_min_amount"))
        high = _amount(service.get("price_max_amount"))
        if low and high:
            return f"{low}–{high}{suffix}"
        return "цена уточняется"
    if price_type == "per_unit":
        amount = _amount(service.get("price_amount"))
        unit = str(service.get("price_unit") or "ед.").strip()
        return (
            f"{amount}{suffix} / {unit}"
            if amount is not None
            else "цена уточняется"
        )
    return "цена уточняется"


def format_catalog(payload: dict[str, Any]) -> str:
    master = payload.get("master") or {}
    title = str(master.get("display_name") or "Прайс").strip()
    services = payload.get("services") or []
    if not services:
        return f"💅 {title}\n\nПрайс пока пуст."
    lines = [f"💅 {title}", ""]
    current_category: str | None = None
    for service in services:
        category = str(service.get("category") or "").strip() or None
        if category != current_category:
            if category:
                lines.append(category)
            current_category = category
        name = str(service.get("public_name") or "Услуга").strip()
        lines.append(f"• {name} — {format_service_price(service)}")
    return "\n".join(lines)[:4000]


def service_picker_keyboard(payload: dict[str, Any]) -> dict[str, Any]:
    binding_id = _binding_id(payload["master"])
    rows: list[list[dict[str, str]]] = []
    base_items = [
        service
        for service in payload.get("services", [])
        if service.get("kind") == "base"
    ]
    for index, service in enumerate(base_items[:40]):
        name = str(service.get("public_name") or "Услуга").strip()
        rows.append(
            [
                {
                    "text": name[:48],
                    "callback_data": f"svc:{binding_id}:{index}",
                }
            ]
        )
    rows.append(
        [{"text": "← Назад", "callback_data": f"master:{binding_id}"}]
    )
    return {"inline_keyboard": rows}


def date_picker_keyboard(
    binding_id: str,
    service_index: int,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    uuid.UUID(binding_id)
    start = today or date.today()
    rows: list[list[dict[str, str]]] = []
    for offset in range(14):
        day = start + timedelta(days=offset)
        label = day.strftime("%d.%m")
        callback = f"day:{binding_id}:{service_index}:{day:%Y%m%d}"
        button = {"text": label, "callback_data": callback}
        if offset % 4 == 0:
            rows.append([])
        rows[-1].append(button)
    rows.append(
        [{"text": "← К услугам", "callback_data": f"book:{binding_id}"}]
    )
    return {"inline_keyboard": rows}


def base_services(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        service
        for service in payload.get("services", [])
        if service.get("kind") == "base"
    ]


def _parse_slot(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise RemoteCallError("client API returned an invalid slot") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RemoteCallError("client API returned a timezone-naive slot")
    return parsed


def compact_slot(value: Any) -> str:
    return _parse_slot(value).strftime("%Y%m%d%H%M")


def slot_picker_keyboard(
    binding_id: str,
    service_index: int,
    starts_at: list[Any],
    *,
    selected_day: date,
) -> dict[str, Any]:
    uuid.UUID(binding_id)
    rows: list[list[dict[str, str]]] = []
    for value in starts_at[:24]:
        parsed = _parse_slot(value)
        if parsed.date() != selected_day:
            continue
        callback = f"slot:{binding_id}:{service_index}:{compact_slot(value)}"
        button = {
            "text": parsed.strftime("%H:%M"),
            "callback_data": callback,
        }
        if len(rows) == 0 or len(rows[-1]) >= 4:
            rows.append([])
        rows[-1].append(button)
    rows.append(
        [
            {
                "text": "← К датам",
                "callback_data": f"svc:{binding_id}:{service_index}",
            }
        ]
    )
    return {"inline_keyboard": rows}


def resolve_current_slot(starts_at: list[Any], compact: str) -> str | None:
    for value in starts_at:
        if compact_slot(value) == compact:
            return str(value)
    return None


def booking_request_idempotency_key(
    binding_id: str,
    service_index: int,
    compact: str,
) -> str:
    uuid.UUID(binding_id)
    return f"tg:{binding_id}:{service_index}:{compact}"


class NailsClientApi:
    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str,
        api_key: str,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _headers(
        self,
        telegram_user_id: int,
        binding_id: str | None = None,
    ) -> dict[str, str]:
        headers = {
            "X-Nails-Client-Internal-Key": self._api_key,
            "X-Telegram-User-ID": str(telegram_user_id),
        }
        if binding_id:
            headers["X-Client-Binding-ID"] = binding_id
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        telegram_user_id: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        binding_id = kwargs.pop("binding_id", None)
        response = self._client.request(
            method,
            f"{self._base_url}{path}",
            headers=self._headers(telegram_user_id, binding_id),
            timeout=15.0,
            **kwargs,
        )
        if response.status_code >= 400:
            raise RemoteCallError(
                f"client API {path} returned {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RemoteCallError(f"client API {path} returned invalid JSON")
        return payload

    def start(
        self,
        telegram_user_id: int,
        token: str,
        public_name: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/client/start",
            telegram_user_id=telegram_user_id,
            json={"start_token": token, "requested_public_name": public_name},
        )

    def context(self, telegram_user_id: int) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/client/context",
            telegram_user_id=telegram_user_id,
        )

    def catalog(
        self,
        telegram_user_id: int,
        binding_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/client/catalog",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
        )

    def slots(
        self,
        telegram_user_id: int,
        binding_id: str,
        day: date,
        service_name: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/client/slots",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
            params={"day": day.isoformat(), "service_name": service_name},
        )

    def create_booking_request(
        self,
        telegram_user_id: int,
        binding_id: str,
        *,
        service_name: str,
        starts_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/client/requests",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
            json={
                "service_name": service_name,
                "addon_names": [],
                "addon_quantities": {},
                "starts_at": starts_at,
                "idempotency_key": idempotency_key,
            },
        )


class TelegramApi:
    def __init__(self, client: httpx.Client, token: str) -> None:
        self._client = client
        self._base_url = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, **payload: Any) -> Any:
        response = self._client.post(
            f"{self._base_url}/{method}",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise RemoteCallError(f"Telegram {method} failed")
        return body.get("result")


class PlatformBot:
    def __init__(self, telegram: TelegramApi, nails: NailsClientApi) -> None:
        self._telegram = telegram
        self._nails = nails

    def _send(
        self,
        chat_id: int,
        text: str,
        keyboard: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": _plain_message(text),
        }
        if keyboard:
            payload["reply_markup"] = keyboard
        self._telegram.call("sendMessage", **payload)

    def _show_context(
        self,
        chat_id: int,
        telegram_user_id: int,
        payload: dict[str, Any],
    ) -> None:
        state = payload.get("state")
        if state == "ready" and payload.get("master"):
            self._send(
                chat_id,
                str(payload.get("message") or ""),
                master_menu_keyboard(payload["master"]),
            )
            return
        if state == "choose_master":
            self._send(
                chat_id,
                str(payload.get("message") or "Выберите мастера."),
                master_picker_keyboard(payload.get("masters") or []),
            )
            return
        self._send(
            chat_id,
            str(payload.get("message") or "Запись сейчас недоступна."),
        )

    def handle_message(self, message: dict[str, Any]) -> None:
        user = message.get("from") or {}
        telegram_user_id = int(user.get("id") or 0)
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        text = str(message.get("text") or "").strip()
        if telegram_user_id <= 0 or chat_id == 0:
            return
        if text.lower().startswith("/start"):
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
        if text.split("@", 1)[0].lower() in {"/masters", "/menu"}:
            context = self._nails.context(telegram_user_id)
            self._show_context(chat_id, telegram_user_id, context)
            return
        self._send(
            chat_id,
            "Откройте /menu или ссылку для записи вашего мастера.",
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
            master_menu_keyboard(master),
        )

    def _catalog_service(
        self,
        telegram_user_id: int,
        binding_id: str,
        index: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        catalog = self._nails.catalog(telegram_user_id, binding_id)
        services = base_services(catalog)
        if not 0 <= index < len(services):
            raise RemoteCallError("service callback is stale")
        return catalog, services[index]

    def handle_callback(self, callback: dict[str, Any]) -> None:
        callback_id = str(callback.get("id") or "")
        user = callback.get("from") or {}
        message = callback.get("message") or {}
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        telegram_user_id = int(user.get("id") or 0)
        data = str(callback.get("data") or "")
        if callback_id:
            self._telegram.call(
                "answerCallbackQuery",
                callback_query_id=callback_id,
            )
        if telegram_user_id <= 0 or chat_id == 0:
            return
        if data == "masters":
            context = self._nails.context(telegram_user_id)
            self._show_context(chat_id, telegram_user_id, context)
            return

        action, _, rest = data.partition(":")
        if action in {"master", "price", "book"}:
            binding_id = str(uuid.UUID(rest))
            if action == "master":
                self._show_master(chat_id, telegram_user_id, binding_id)
            elif action == "price":
                catalog = self._nails.catalog(telegram_user_id, binding_id)
                self._send(
                    chat_id,
                    format_catalog(catalog),
                    master_menu_keyboard(catalog["master"]),
                )
            else:
                catalog = self._nails.catalog(telegram_user_id, binding_id)
                self._send(
                    chat_id,
                    "Выберите услугу:",
                    service_picker_keyboard(catalog),
                )
            return

        if action == "svc":
            binding_id, index_text = rest.rsplit(":", 1)
            binding_id = str(uuid.UUID(binding_id))
            index = int(index_text)
            _catalog, service = self._catalog_service(
                telegram_user_id,
                binding_id,
                index,
            )
            name = str(service.get("public_name") or "Услуга")
            self._send(
                chat_id,
                f"{name}\nВыберите дату:",
                date_picker_keyboard(binding_id, index),
            )
            return

        if action == "day":
            binding_id, index_text, compact_day = rest.split(":", 2)
            binding_id = str(uuid.UUID(binding_id))
            index = int(index_text)
            selected_day = date.fromisoformat(
                f"{compact_day[0:4]}-{compact_day[4:6]}-{compact_day[6:8]}"
            )
            _catalog, service = self._catalog_service(
                telegram_user_id,
                binding_id,
                index,
            )
            service_name = str(service.get("public_name") or "")
            slots = self._nails.slots(
                telegram_user_id,
                binding_id,
                selected_day,
                service_name,
            )
            starts = slots.get("starts_at") or []
            if starts:
                text = f"Свободное время на {selected_day:%d.%m}:"
                keyboard = slot_picker_keyboard(
                    binding_id,
                    index,
                    starts,
                    selected_day=selected_day,
                )
            else:
                text = f"На {selected_day:%d.%m} свободного времени нет."
                keyboard = date_picker_keyboard(binding_id, index)
            self._send(chat_id, text, keyboard)
            return

        if action == "slot":
            binding_id, index_text, compact = rest.split(":", 2)
            binding_id = str(uuid.UUID(binding_id))
            index = int(index_text)
            if len(compact) != 12 or not compact.isdigit():
                raise RemoteCallError("slot callback is invalid")
            selected_day = date.fromisoformat(
                f"{compact[0:4]}-{compact[4:6]}-{compact[6:8]}"
            )
            catalog, service = self._catalog_service(
                telegram_user_id,
                binding_id,
                index,
            )
            service_name = str(service.get("public_name") or "")
            slots = self._nails.slots(
                telegram_user_id,
                binding_id,
                selected_day,
                service_name,
            )
            starts = slots.get("starts_at") or []
            starts_at = resolve_current_slot(starts, compact)
            if starts_at is None:
                self._send(
                    chat_id,
                    "Это время уже недоступно. Выберите другое.",
                    slot_picker_keyboard(
                        binding_id,
                        index,
                        starts,
                        selected_day=selected_day,
                    ),
                )
                return
            request = self._nails.create_booking_request(
                telegram_user_id,
                binding_id,
                service_name=service_name,
                starts_at=starts_at,
                idempotency_key=booking_request_idempotency_key(
                    binding_id,
                    index,
                    compact,
                ),
            )
            if request.get("status") != "pending":
                raise RemoteCallError("client API returned an unexpected request status")
            parsed = _parse_slot(starts_at)
            self._send(
                chat_id,
                "✅ Заявка отправлена\n"
                f"{service_name}\n"
                f"{parsed:%d.%m} в {parsed:%H:%M}\n\n"
                "Мастер подтвердит запись. Пока время не забронировано.",
                master_menu_keyboard(catalog["master"]),
            )

    def handle_update(self, update: dict[str, Any]) -> None:
        if isinstance(update.get("message"), dict):
            self.handle_message(update["message"])
        elif isinstance(update.get("callback_query"), dict):
            self.handle_callback(update["callback_query"])


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    config = BotConfig.from_env()
    offset = 0
    with httpx.Client() as client:
        telegram = TelegramApi(client, config.telegram_token)
        nails = NailsClientApi(
            client,
            base_url=config.client_api_url,
            api_key=config.client_api_key,
        )
        bot = PlatformBot(telegram, nails)
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
