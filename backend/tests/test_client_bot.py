from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.client_bot import (
    BotConfig,
    ClientBotConfigError,
    NailsClientApi,
    PlatformBot,
    base_services,
    booking_request_idempotency_key,
    compact_slot,
    date_picker_keyboard,
    format_catalog,
    format_service_price,
    master_menu_keyboard,
    master_picker_keyboard,
    parse_start_token,
    resolve_current_slot,
    service_picker_keyboard,
    slot_picker_keyboard,
    telegram_public_name,
)

BINDING_A = "11111111-1111-4111-8111-111111111111"
BINDING_B = "22222222-2222-4222-8222-222222222222"


def _master(binding_id: str, name: str) -> dict[str, str | None]:
    return {
        "binding_id": binding_id,
        "display_name": name,
        "public_contact": None,
    }


def _catalog() -> dict[str, object]:
    return {
        "master": _master(BINDING_A, "Ногти у Насти"),
        "services": [
            {
                "public_name": "Маникюр",
                "kind": "base",
                "price_type": "fixed",
                "price_amount": "2700.00",
                "currency": "RUB",
                "category": "Маникюр",
            },
            {
                "public_name": "Снятие",
                "kind": "addon",
                "price_type": "fixed",
                "price_amount": "300.00",
                "currency": "RUB",
                "category": "Допы",
            },
        ],
    }


def test_parse_start_token_supports_telegram_command_suffix():
    assert parse_start_token("/start opaque-token") == "opaque-token"
    assert parse_start_token("/start@client_bot opaque-token") == "opaque-token"
    assert parse_start_token("/start") is None
    assert parse_start_token("/menu") is None


def test_client_public_name_uses_client_identity_only():
    assert telegram_public_name({"first_name": "Анна", "last_name": "Иванова"}) == (
        "Анна Иванова"
    )
    assert telegram_public_name({"username": "anna"}) == "@anna"
    assert telegram_public_name({}) == "Клиентка"


def test_master_picker_exposes_binding_handle_not_master_telegram_id():
    keyboard = master_picker_keyboard(
        [_master(BINDING_A, "Мастер А"), _master(BINDING_B, "Мастер Б")]
    )
    serialized = str(keyboard)
    assert f"master:{BINDING_A}" in serialized
    assert f"master:{BINDING_B}" in serialized
    assert "telegram_user_id" not in serialized
    assert "7132701825" not in serialized


def test_master_menu_callback_data_stays_within_telegram_limit():
    keyboard = master_menu_keyboard(_master(BINDING_A, "Мастер А"))
    callbacks = [
        button["callback_data"]
        for row in keyboard["inline_keyboard"]
        for button in row
    ]
    assert callbacks == [f"price:{BINDING_A}", f"book:{BINDING_A}", "masters"]
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks)


def test_price_formatting_uses_public_price_contract():
    assert format_service_price(
        {"price_type": "fixed", "price_amount": "2700.00", "currency": "RUB"}
    ) == "2 700 ₽"
    assert format_service_price(
        {
            "price_type": "range",
            "price_min_amount": "2500",
            "price_max_amount": "3000",
            "currency": "RUB",
        }
    ) == "2 500–3 000 ₽"
    assert format_service_price(
        {
            "price_type": "per_unit",
            "price_amount": "100",
            "price_unit": "ноготь",
            "currency": "RUB",
        }
    ) == "100 ₽ / ноготь"
    assert format_service_price({"price_type": "on_request", "currency": "RUB"}) == (
        "цена уточняется"
    )


def test_catalog_contains_only_public_projection():
    text = format_catalog(_catalog())
    assert "Ногти у Насти" in text
    assert "Маникюр — 2 700 ₽" in text
    assert "Снятие — 300 ₽" in text
    assert "owner_user_id" not in text
    assert "telegram_user_id" not in text


def test_service_and_date_picker_keep_owner_out_of_callback_contract():
    catalog = _catalog()
    service_keyboard = service_picker_keyboard(catalog)
    callbacks = [
        button["callback_data"]
        for row in service_keyboard["inline_keyboard"]
        for button in row
    ]
    assert f"svc:{BINDING_A}:0" in callbacks
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks)

    dates = date_picker_keyboard(BINDING_A, 0, today=date(2026, 7, 28))
    date_callbacks = [
        button["callback_data"]
        for row in dates["inline_keyboard"]
        for button in row
        if button["callback_data"].startswith("day:")
    ]
    assert date_callbacks[0] == f"day:{BINDING_A}:0:20260728"
    assert len(date_callbacks) == 14
    assert all(len(value.encode("utf-8")) <= 64 for value in date_callbacks)


def test_slot_picker_uses_binding_handle_and_compact_timestamp_only():
    starts = [
        "2026-08-10T11:00:00+02:00",
        "2026-08-10T12:30:00+02:00",
    ]
    keyboard = slot_picker_keyboard(
        BINDING_A,
        0,
        starts,
        selected_day=date(2026, 8, 10),
    )
    callbacks = [
        button["callback_data"]
        for row in keyboard["inline_keyboard"]
        for button in row
    ]
    assert f"slot:{BINDING_A}:0:202608101100" in callbacks
    assert f"slot:{BINDING_A}:0:202608101230" in callbacks
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks)
    assert "owner_user_id" not in str(keyboard)


def test_slot_resolution_reuses_current_api_value():
    starts = ["2026-08-10T11:00:00+02:00"]
    compact = compact_slot(starts[0])
    assert compact == "202608101100"
    assert resolve_current_slot(starts, compact) == starts[0]
    assert resolve_current_slot(starts, "202608101200") is None
    assert booking_request_idempotency_key(BINDING_A, 0, compact) == (
        f"tg:{BINDING_A}:0:202608101100"
    )


def test_base_services_excludes_addons():
    services = base_services(_catalog())
    assert [service["public_name"] for service in services] == ["Маникюр"]


def test_client_api_posts_booking_request_without_owner_or_client_override():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["binding"] = request.headers.get("X-Client-Binding-ID")
        seen["telegram"] = request.headers.get("X-Telegram-User-ID")
        seen["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "id": "33333333-3333-4333-8333-333333333333",
                "status": "pending",
                "service_name": "Маникюр",
                "addon_names": [],
                "addon_quantities": {},
                "starts_at": "2026-08-10T11:00:00+02:00",
                "booking_id": None,
                "created_at": "2026-07-29T00:00:00+00:00",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        api = NailsClientApi(http, base_url="http://nails-api", api_key="c" * 64)
        payload = api.create_booking_request(
            900001,
            BINDING_A,
            service_name="Маникюр",
            starts_at="2026-08-10T11:00:00+02:00",
            idempotency_key="request-key",
        )

    assert payload["status"] == "pending"
    assert seen["method"] == "POST"
    assert seen["url"] == "http://nails-api/api/v1/client/requests"
    assert seen["binding"] == BINDING_A
    assert seen["telegram"] == "900001"
    body = str(seen["body"])
    assert '"service_name":"Маникюр"' in body
    assert '"addon_names":[]' in body
    assert '"owner_user_id"' not in body
    assert '"client_id"' not in body


class _FakeTelegram:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call(self, method: str, **payload):
        self.calls.append((method, payload))
        return None


class _FakeNails:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    def catalog(self, telegram_user_id: int, binding_id: str):
        assert telegram_user_id == 900001
        assert binding_id == BINDING_A
        return _catalog()

    def slots(self, telegram_user_id, binding_id, day, service_name):
        assert telegram_user_id == 900001
        assert binding_id == BINDING_A
        assert day == date(2026, 8, 10)
        assert service_name == "Маникюр"
        return {"starts_at": ["2026-08-10T11:00:00+02:00"]}

    def create_booking_request(self, telegram_user_id, binding_id, **payload):
        self.created.append(
            {
                "telegram_user_id": telegram_user_id,
                "binding_id": binding_id,
                **payload,
            }
        )
        return {"status": "pending"}


def test_slot_callback_rechecks_slot_and_submits_pending_request():
    telegram = _FakeTelegram()
    nails = _FakeNails()
    bot = PlatformBot(telegram, nails)  # type: ignore[arg-type]

    bot.handle_callback(
        {
            "id": "callback-1",
            "from": {"id": 900001},
            "message": {"chat": {"id": 900001}},
            "data": f"slot:{BINDING_A}:0:202608101100",
        }
    )

    assert nails.created == [
        {
            "telegram_user_id": 900001,
            "binding_id": BINDING_A,
            "service_name": "Маникюр",
            "starts_at": "2026-08-10T11:00:00+02:00",
            "idempotency_key": f"tg:{BINDING_A}:0:202608101100",
        }
    ]
    sent = [payload for method, payload in telegram.calls if method == "sendMessage"]
    assert len(sent) == 1
    assert "Заявка отправлена" in str(sent[0]["text"])
    assert "Пока время не забронировано" in str(sent[0]["text"])


def test_bot_config_requires_token_and_separate_client_key(monkeypatch):
    monkeypatch.delenv("CLIENT_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("CLIENT_INTERNAL_API_KEY", "c" * 64)
    with pytest.raises(ClientBotConfigError, match="CLIENT_TELEGRAM_BOT_TOKEN"):
        BotConfig.from_env()

    monkeypatch.setenv("CLIENT_TELEGRAM_BOT_TOKEN", "123:test")
    monkeypatch.setenv("CLIENT_INTERNAL_API_KEY", "short")
    with pytest.raises(ClientBotConfigError, match="CLIENT_INTERNAL_API_KEY"):
        BotConfig.from_env()
