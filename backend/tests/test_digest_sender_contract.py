from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

import httpx


def _load_sender() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "ops" / "digest" / "send.py"
    spec = importlib.util.spec_from_file_location("nails_digest_sender", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _booking(**overrides):
    value = {
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "addon_names": ["Снятие"],
        "starts_at": "2026-07-19T11:00:00+03:00",
        "ends_at": "2026-07-19T13:00:00+03:00",
        "price_type": "fixed",
        "price_amount": "2700.00",
        "price_min_amount": "2700.00",
        "price_max_amount": "2700.00",
        "price_unit": None,
        "price_confirmed": True,
        "currency": "RUB",
    }
    value.update(overrides)
    return value


def test_message_uses_public_fields_and_never_turns_unknown_price_into_zero():
    sender = _load_sender()
    message = sender._message(
        [
            _booking(),
            _booking(
                client_public_name="Лена",
                service_name="Дизайн",
                addon_names=[],
                price_type="on_request",
                price_amount=None,
                price_min_amount=None,
                price_max_amount=None,
                price_confirmed=False,
            ),
        ],
        ZoneInfo("Europe/Moscow"),
        date(2026, 7, 19),
    )

    assert "Итоги дня — 19.07.2026" in message
    assert "Заработок за день: от 2700 ₽" in message
    assert "Анна" in message
    assert "Маникюр + Снятие" in message
    assert "2700 ₽" in message
    assert "Индивидуальная цена" in message
    assert "1 — 1700" in message
    assert "Нэйли уже посчитала день" in message
    assert "Итоговая сумма не указана" not in message
    assert "общую подтверждённую сумму" not in message
    assert "\nОриентир: 0 ₽" not in message
    assert "claim_id" not in message
    assert "booking_id" not in message


def test_sender_keeps_bot_credential_outside_backend_requests(monkeypatch):
    sender = _load_sender()
    backend_calls = []
    ack_calls = []
    telegram_calls = []

    def fake_request_json(client, method, path, *, headers, json_body=None):
        del client
        backend_calls.append((method, path, headers, json_body))
        return {
            "claimed": True,
            "claim_id": "11111111-1111-4111-8111-111111111111",
            "local_day": "2026-07-19",
            "bookings": [_booking()],
        }

    def fake_ack(client, api_key, telegram_user_id, claim_id, *, sent):
        del client
        ack_calls.append((api_key, telegram_user_id, claim_id, sent))
        return {"changed": True, "sent": sent, "bookings_count": 1}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    class Client:
        def post(self, url, *, json):
            telegram_calls.append((url, json))
            return Response()

    monkeypatch.setattr(sender, "_request_json", fake_request_json)
    monkeypatch.setattr(sender, "_ack", fake_ack)

    result = sender._send_owner_digest(
        Client(),
        "internal-key",
        "bot-secret",
        700000001,
        datetime(2026, 7, 19, 23, 30, tzinfo=ZoneInfo("Europe/Moscow")),
    )

    assert result is True
    assert len(backend_calls) == 1
    assert "bot-secret" not in repr(backend_calls)
    assert telegram_calls[0][0].endswith("/botbot-secret/sendMessage")
    assert telegram_calls[0][1]["chat_id"] == 700000001
    assert "19.07.2026" in telegram_calls[0][1]["text"]
    assert "Заработок за день: 2700 ₽" in telegram_calls[0][1]["text"]
    assert ack_calls == [
        (
            "internal-key",
            700000001,
            "11111111-1111-4111-8111-111111111111",
            True,
        )
    ]


def test_known_telegram_failure_releases_claim(monkeypatch):
    sender = _load_sender()
    ack_calls = []

    monkeypatch.setattr(
        sender,
        "_request_json",
        lambda *args, **kwargs: {
            "claimed": True,
            "claim_id": "11111111-1111-4111-8111-111111111111",
            "local_day": "2026-07-19",
            "bookings": [_booking()],
        },
    )

    def fake_ack(client, api_key, telegram_user_id, claim_id, *, sent):
        del client
        ack_calls.append((api_key, telegram_user_id, claim_id, sent))
        return {"changed": True, "sent": sent, "bookings_count": 1}

    class Response:
        request = httpx.Request("POST", "https://api.telegram.org")

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "failed",
                request=self.request,
                response=httpx.Response(500, request=self.request),
            )

    class Client:
        def post(self, url, *, json):
            del url, json
            return Response()

    monkeypatch.setattr(sender, "_ack", fake_ack)

    try:
        sender._send_owner_digest(
            Client(),
            "internal-key",
            "bot-secret",
            700000001,
            datetime(2026, 7, 19, 23, 30, tzinfo=ZoneInfo("Europe/Moscow")),
        )
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("Telegram failure must be propagated")

    assert ack_calls == [
        (
            "internal-key",
            700000001,
            "11111111-1111-4111-8111-111111111111",
            False,
        )
    ]
