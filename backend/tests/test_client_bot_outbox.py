from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.client_bot_outbox import (
    ClientBotRuntimeState,
    NotificationDrainer,
    OutboxRuntimeConfig,
    format_client_appointment_time,
    notification_text,
    telegram_failure,
)


class FakeTelegram:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call(self, method: str, **payload):
        self.calls.append((method, payload))
        if self.error is not None:
            raise self.error
        return {"message_id": 1}


class FakeApi:
    def __init__(self) -> None:
        self.acks: list[tuple[str, str, str | None]] = []

    def ack(self, claim_id: str, outcome: str, error_code: str | None = None) -> None:
        self.acks.append((claim_id, outcome, error_code))


def _config(tmp_path: Path) -> OutboxRuntimeConfig:
    return OutboxRuntimeConfig(
        client_api_url="http://127.0.0.1:8210",
        client_api_key="c" * 64,
        status_path=tmp_path / "status.json",
        drain_interval_seconds=0.01,
        per_chat_interval_seconds=0.01,
    )


def _claim(event_type: str = "approved") -> dict[str, object]:
    return {
        "claim_id": "11111111-1111-4111-8111-111111111111",
        "telegram_user_id": 900000001,
        "event_type": event_type,
        "payload": {
            "service_name": "Маникюр",
            "starts_at": "2026-08-01T12:00:00+02:00",
        },
    }


def test_successful_delivery_acks_sent_and_writes_health(tmp_path):
    telegram = FakeTelegram()
    api = FakeApi()
    state = ClientBotRuntimeState()
    drainer = NotificationDrainer(telegram, api, _config(tmp_path), state)

    drainer._deliver(_claim())

    assert api.acks == [
        ("11111111-1111-4111-8111-111111111111", "sent", None)
    ]
    assert telegram.calls[0][0] == "sendMessage"
    assert "Запись подтверждена" in telegram.calls[0][1]["text"]
    assert state.sent_count == 1
    assert state.last_delivery_at is not None
    assert _config(tmp_path).status_path.exists()


def test_blocked_bot_marks_notification_unreachable(tmp_path):
    request = httpx.Request("POST", "https://api.telegram.org/botX/sendMessage")
    response = httpx.Response(403, request=request)
    telegram = FakeTelegram(httpx.HTTPStatusError("blocked", request=request, response=response))
    api = FakeApi()
    state = ClientBotRuntimeState()
    drainer = NotificationDrainer(telegram, api, _config(tmp_path), state)

    drainer._deliver(_claim("rejected"))

    assert api.acks == [
        (
            "11111111-1111-4111-8111-111111111111",
            "unreachable",
            "telegram_http_403",
        )
    ]
    assert state.unreachable_count == 1


def test_rate_limit_is_retry_not_unreachable():
    request = httpx.Request("POST", "https://api.telegram.org/botX/sendMessage")
    response = httpx.Response(429, request=request)
    outcome, code = telegram_failure(
        httpx.HTTPStatusError("limited", request=request, response=response)
    )
    assert outcome == "retry"
    assert code == "telegram_rate_limited"


def test_utc_time_is_formatted_in_master_timezone():
    timezone = ZoneInfo("Europe/Moscow")

    assert (
        format_client_appointment_time(
            "2026-08-11T10:45:00+00:00",
            timezone=timezone,
        )
        == "11.08 в 13:45"
    )


def test_approval_notification_never_contains_raw_iso():
    approved = notification_text(
        "approved",
        {
            "service_name": "Маникюр",
            "starts_at": "2026-08-11T10:45:00+00:00",
        },
        timezone=ZoneInfo("Europe/Moscow"),
    )

    assert "Запись подтверждена" in approved
    assert "11.08 в 13:45" in approved
    assert "2026-08-11T10:45:00+00:00" not in approved


def test_notification_copy_is_transactional_and_bounded():
    approved = notification_text(
        "approved",
        {"service_name": "Маникюр", "starts_at": "2026-08-01T12:00:00+02:00"},
    )
    rejected = notification_text("rejected", {"service_name": "Маникюр"})
    cancelled = notification_text("cancelled", {"service_name": "Маникюр"})
    assert "подтверждена" in approved
    assert "не смог" in rejected
    assert "отменена" in cancelled
    assert "T12:00:00" not in approved
    assert len(approved) < 512
