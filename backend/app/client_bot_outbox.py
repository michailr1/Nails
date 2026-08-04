from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.client_bot import TelegramApi
from app.services.scheduling_common import app_timezone


@dataclass(frozen=True, slots=True)
class OutboxRuntimeConfig:
    client_api_url: str
    client_api_key: str
    status_path: Path
    drain_interval_seconds: float
    per_chat_interval_seconds: float

    @classmethod
    def from_env(cls) -> OutboxRuntimeConfig:
        api_key = os.getenv("CLIENT_INTERNAL_API_KEY", "").strip()
        if len(api_key) < 32:
            raise RuntimeError("CLIENT_INTERNAL_API_KEY must contain at least 32 characters")
        return cls(
            client_api_url=os.getenv(
                "NAILS_CLIENT_API_URL", "http://127.0.0.1:8210"
            ).rstrip("/"),
            client_api_key=api_key,
            status_path=Path(
                os.getenv("CLIENT_BOT_STATUS_PATH", "/run/nails/client-bot-status.json")
            ),
            drain_interval_seconds=max(
                0.1, float(os.getenv("CLIENT_OUTBOX_DRAIN_INTERVAL_SECONDS", "0.5"))
            ),
            per_chat_interval_seconds=max(
                0.05,
                float(os.getenv("CLIENT_TELEGRAM_PER_CHAT_INTERVAL_SECONDS", "1.1")),
            ),
        )


class ClientNotificationApi:
    def __init__(self, client: httpx.Client, config: OutboxRuntimeConfig) -> None:
        self._client = client
        self._base_url = config.client_api_url
        self._headers = {"X-Nails-Client-Internal-Key": config.client_api_key}

    def claim(self) -> dict[str, Any]:
        response = self._client.post(
            f"{self._base_url}/api/v1/client/notifications/internal/claim",
            headers=self._headers,
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("notification claim returned invalid payload")
        return payload

    def ack(self, claim_id: str, outcome: str, error_code: str | None = None) -> None:
        response = self._client.post(
            f"{self._base_url}/api/v1/client/notifications/internal/ack",
            headers=self._headers,
            json={"claim_id": claim_id, "outcome": outcome, "error_code": error_code},
            timeout=10.0,
        )
        response.raise_for_status()


@dataclass(slots=True)
class ClientBotRuntimeState:
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_poll_at: str | None = None
    last_delivery_at: str | None = None
    sent_count: int = 0
    retry_count: int = 0
    unreachable_count: int = 0
    failed_count: int = 0
    last_error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def mark_poll(self) -> None:
        with self._lock:
            self.last_poll_at = datetime.now(UTC).isoformat()
            self.last_error = None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "started_at": self.started_at,
                "last_poll_at": self.last_poll_at,
                "last_delivery_at": self.last_delivery_at,
                "sent_count": self.sent_count,
                "retry_count": self.retry_count,
                "unreachable_count": self.unreachable_count,
                "failed_count": self.failed_count,
                "last_error": self.last_error,
            }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.snapshot(), ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temporary, path)


def format_client_appointment_time(
    value: object,
    *,
    timezone: ZoneInfo | None = None,
) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    local = parsed.astimezone(timezone or app_timezone())
    return local.strftime("%d.%m в %H:%M")


def notification_text(
    event_type: str,
    payload: dict[str, Any],
    *,
    timezone: ZoneInfo | None = None,
) -> str:
    service = str(payload.get("service_name") or "Запись")
    starts_at = format_client_appointment_time(
        payload.get("starts_at"), timezone=timezone
    )
    details = f"\n{service}" + (f"\n{starts_at}" if starts_at else "")
    if event_type == "approved":
        return f"Запись подтверждена ✅{details}"
    if event_type == "rejected":
        return f"Мастер не смог подтвердить заявку.{details}"
    if event_type == "cancelled":
        return f"Заявка отменена.{details}"
    raise ValueError("unsupported notification event")


def telegram_failure(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in {400, 403}:
            return "unreachable", f"telegram_http_{code}"
        if code == 429:
            return "retry", "telegram_rate_limited"
        return "retry", f"telegram_http_{code}"
    return "retry", "telegram_delivery_error"


class NotificationDrainer:
    def __init__(
        self,
        telegram: TelegramApi,
        api: ClientNotificationApi,
        config: OutboxRuntimeConfig,
        state: ClientBotRuntimeState,
    ) -> None:
        self._telegram = telegram
        self._api = api
        self._config = config
        self._state = state
        self._stop = threading.Event()
        self._last_send_by_chat: dict[int, float] = {}

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                claim = self._api.claim()
                if not claim.get("claimed"):
                    self._stop.wait(self._config.drain_interval_seconds)
                    continue
                self._deliver(claim)
            except Exception as exc:
                with self._state._lock:
                    self._state.failed_count += 1
                    self._state.last_error = type(exc).__name__
                self._state.write(self._config.status_path)
                self._stop.wait(1.0)

    def _deliver(self, claim: dict[str, Any]) -> None:
        claim_id = str(claim["claim_id"])
        chat_id = int(claim["telegram_user_id"])
        last_send = self._last_send_by_chat.get(chat_id, 0.0)
        delay = self._config.per_chat_interval_seconds - (time.monotonic() - last_send)
        if delay > 0:
            self._stop.wait(delay)
        if self._stop.is_set():
            self._api.ack(claim_id, "retry", "runtime_stopping")
            return
        try:
            self._telegram.call(
                "sendMessage",
                chat_id=chat_id,
                text=notification_text(
                    str(claim["event_type"]), dict(claim.get("payload") or {})
                ),
            )
        except Exception as exc:
            outcome, error_code = telegram_failure(exc)
            self._api.ack(claim_id, outcome, error_code)
            with self._state._lock:
                if outcome == "unreachable":
                    self._state.unreachable_count += 1
                else:
                    self._state.retry_count += 1
                self._state.last_error = error_code
            self._state.write(self._config.status_path)
            return

        self._last_send_by_chat[chat_id] = time.monotonic()
        self._api.ack(claim_id, "sent")
        with self._state._lock:
            self._state.sent_count += 1
            self._state.last_delivery_at = datetime.now(UTC).isoformat()
            self._state.last_error = None
        self._state.write(self._config.status_path)
