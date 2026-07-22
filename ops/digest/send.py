#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

logger = logging.getLogger("nails-finalization-digest")
_MAX_MESSAGE_LENGTH = 3900
_MAX_LONG_ABSENT_CLIENTS = 5


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


def _telegram_token() -> str:
    value = (
        os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        or os.getenv("TELEGRAM_TOKEN", "").strip()
    )
    if not value:
        raise RuntimeError("Telegram token is not configured")
    return value


def _timezone() -> ZoneInfo:
    value = os.getenv("APP_TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("APP_TIMEZONE is invalid") from exc


def _api_base() -> str:
    return os.getenv("NAILS_API_BASE", "http://127.0.0.1:8210").strip().rstrip("/")


def _headers(api_key: str, telegram_user_id: int | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Internal-Key": api_key,
        "X-Request-ID": f"finalization-digest-{uuid.uuid4()}",
    }
    if telegram_user_id is not None:
        headers["X-Telegram-User-ID"] = str(telegram_user_id)
    return headers


def _request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(
        method,
        f"{_api_base()}{path}",
        headers=headers,
        json=json_body,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("backend returned a non-object response")
    return payload


def _money(value: Any, currency: str) -> str:
    amount = Decimal(str(value))
    normalized = format(amount.quantize(Decimal("0.01")), "f")
    if normalized.endswith(".00"):
        normalized = normalized[:-3]
    suffix = "₽" if currency == "RUB" else currency
    return f"{normalized} {suffix}"


def _price_text(item: dict[str, Any]) -> str:
    price_type = item.get("price_type")
    currency = str(item.get("currency") or "RUB")
    if item.get("price_amount") is not None:
        prefix = "от " if price_type in {"range", "per_unit", "on_request"} else ""
        return f"Ориентир: {prefix}{_money(item['price_amount'], currency)}"
    minimum = item.get("price_min_amount")
    if minimum is not None:
        return f"Ориентир: от {_money(minimum, currency)}"
    return "Индивидуальная цена"


def _daily_earnings_line(bookings: list[dict[str, Any]]) -> str:
    total = Decimal(0)
    currency = "RUB"
    estimated = False
    for item in bookings:
        currency = str(item.get("currency") or currency)
        amount = item.get("price_amount")
        if amount is None:
            amount = item.get("price_min_amount")
        if amount is None:
            estimated = True
            continue
        total += Decimal(str(amount))
        if item.get("price_type") != "fixed" or item.get("price_confirmed") is not True:
            estimated = True
    prefix = "от " if estimated else ""
    return f"Заработок за день: {prefix}{_money(total, currency)}"


def _long_absent_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return []
    lines = ["", "💡 Давно не были"]
    for item in items[:_MAX_LONG_ABSENT_CLIENTS]:
        last_visit = date.fromisoformat(str(item["last_visit_date"]))
        weeks = max(1, int(item["days_since_last_visit"]) // 7)
        lines.append(
            f"• {item['client_name']} — последний раз {last_visit:%d.%m}, "
            f"{weeks} нед. назад"
        )
    remaining = len(items) - _MAX_LONG_ABSENT_CLIENTS
    if remaining > 0:
        lines.append(f"И ещё {remaining} — полный список есть в кабинете.")
    lines.append("Нэйли никому не пишет сама — это только подсказка вам.")
    return lines


def _message(
    bookings: list[dict[str, Any]],
    timezone: ZoneInfo,
    local_day: date,
    long_absent_clients: list[dict[str, Any]] | None = None,
) -> str:
    lines = [
        f"🌙 Итоги дня — {local_day:%d.%m.%Y}",
        _daily_earnings_line(bookings),
        "",
    ]
    for index, item in enumerate(bookings, start=1):
        starts_at = datetime.fromisoformat(str(item["starts_at"])).astimezone(timezone)
        ends_at = datetime.fromisoformat(str(item["ends_at"])).astimezone(timezone)
        addons = item.get("addon_names")
        addon_text = ""
        if isinstance(addons, list) and addons:
            addon_text = " + " + ", ".join(str(value) for value in addons)
        lines.extend(
            (
                f"{index}. {starts_at:%H:%M}–{ends_at:%H:%M} · "
                f"{item['client_public_name']} · {item['service_name']}{addon_text}",
                _price_text(item),
                "",
            )
        )
    lines.extend(
        (
            "Нэйли уже посчитала день по сохранённым ценам из записей.",
            "Если фактическая сумма отличалась, напишите по номеру или имени, "
            "например: «1 — 1700» или «у Марины 1700». Неявку можно отметить: "
            "«2 — не пришла».",
        )
    )
    lines.extend(_long_absent_lines(long_absent_clients or []))
    return "\n".join(lines)[:_MAX_MESSAGE_LENGTH]


def _ack(
    client: httpx.Client,
    api_key: str,
    telegram_user_id: int,
    claim_id: str,
    *,
    sent: bool,
) -> dict[str, Any]:
    return _request_json(
        client,
        "POST",
        "/api/v1/scheduling/finalization-digest/ack",
        headers=_headers(api_key, telegram_user_id),
        json_body={"claim_id": claim_id, "sent": sent},
    )


def _send_owner_digest(
    client: httpx.Client,
    api_key: str,
    token: str,
    telegram_user_id: int,
    now: datetime,
) -> bool:
    claim = _request_json(
        client,
        "POST",
        "/api/v1/scheduling/finalization-digest/claim",
        headers=_headers(api_key, telegram_user_id),
        json_body={"local_day": now.date().isoformat()},
    )
    if claim.get("claimed") is not True:
        return False
    claim_id = claim.get("claim_id")
    bookings = claim.get("bookings")
    long_absent_clients = claim.get("long_absent_clients", [])
    claimed_local_day = claim.get("local_day")
    if (
        not isinstance(claim_id, str)
        or not isinstance(bookings, list)
        or not bookings
        or not isinstance(long_absent_clients, list)
        or not isinstance(claimed_local_day, str)
    ):
        raise ValueError("backend returned an invalid digest claim")
    try:
        local_day = date.fromisoformat(claimed_local_day)
    except ValueError as exc:
        raise ValueError("backend returned an invalid digest local day") from exc

    try:
        response = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": telegram_user_id,
                "text": _message(
                    bookings,
                    now.tzinfo or _timezone(),
                    local_day,
                    long_absent_clients,
                ),
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise ValueError("Telegram rejected the digest")
    except (httpx.HTTPError, ValueError):
        _ack(
            client,
            api_key,
            telegram_user_id,
            claim_id,
            sent=False,
        )
        raise

    ack = _ack(
        client,
        api_key,
        telegram_user_id,
        claim_id,
        sent=True,
    )
    if ack.get("sent") is not True:
        raise ValueError("backend did not acknowledge the sent digest")
    return True


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    api_key = _required_env("INTERNAL_API_KEY")
    token = _telegram_token()
    timezone = _timezone()
    now = datetime.now(timezone)

    sent_count = 0
    with httpx.Client(timeout=15.0) as client:
        owners = _request_json(
            client,
            "GET",
            "/api/v1/scheduling/finalization-digest/owners",
            headers=_headers(api_key),
        )
        user_ids = owners.get("telegram_user_ids")
        if not isinstance(user_ids, list):
            raise ValueError("backend returned an invalid owners response")
        for value in user_ids:
            if not isinstance(value, int) or value <= 0:
                raise ValueError("backend returned an invalid Telegram user ID")
            if _send_owner_digest(client, api_key, token, value, now):
                sent_count += 1

    logger.info("DIGEST_OK=true owners_sent=%s local_day=%s", sent_count, now.date())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        logger.exception("Finalization digest failed safely")
        raise SystemExit(1) from None
