#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger("nails-client-forward")


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


def _api_base() -> str:
    return os.getenv("NAILS_API_BASE", "http://127.0.0.1:8210").strip().rstrip("/")


def _headers(api_key: str) -> dict[str, str]:
    return {
        "X-Nails-Internal-Key": api_key,
        "X-Request-ID": f"client-forward-{uuid.uuid4()}",
    }


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


def _ack(
    client: httpx.Client,
    api_key: str,
    claim_id: str,
    *,
    sent: bool,
) -> None:
    payload = _request_json(
        client,
        "POST",
        "/api/v1/client/contact-forward/internal/ack",
        headers=_headers(api_key),
        json_body={"claim_id": claim_id, "sent": sent},
    )
    if payload.get("changed") is not True:
        raise ValueError("backend did not acknowledge contact forward")


def _format_message(client_name: str, text: str) -> str:
    return (
        "💬 Сообщение из клиентского бота\n"
        f"Клиентка: {client_name}\n\n"
        f"{text}"
    )[:3900]


def _send_one(
    client: httpx.Client,
    *,
    api_key: str,
    telegram_token: str,
) -> bool:
    claim = _request_json(
        client,
        "POST",
        "/api/v1/client/contact-forward/internal/claim",
        headers=_headers(api_key),
    )
    if claim.get("claimed") is not True:
        return False

    claim_id = claim.get("claim_id")
    master_telegram_user_id = claim.get("master_telegram_user_id")
    client_name = claim.get("client_public_name")
    message_text = claim.get("message_text")
    if (
        not isinstance(claim_id, str)
        or not isinstance(master_telegram_user_id, int)
        or master_telegram_user_id <= 0
        or not isinstance(client_name, str)
        or not client_name.strip()
        or not isinstance(message_text, str)
        or not message_text.strip()
    ):
        raise ValueError("backend returned an invalid contact forward claim")

    try:
        response = client.post(
            f"https://api.telegram.org/bot{telegram_token}/sendMessage",
            json={
                "chat_id": master_telegram_user_id,
                "text": _format_message(client_name.strip(), message_text.strip()),
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise ValueError("Telegram rejected contact forward")
    except (httpx.HTTPError, ValueError):
        _ack(client, api_key, claim_id, sent=False)
        raise

    _ack(client, api_key, claim_id, sent=True)
    return True


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    api_key = _required_env("INTERNAL_API_KEY")
    telegram_token = _telegram_token()
    idle_seconds = float(os.getenv("CLIENT_FORWARD_IDLE_SECONDS", "2"))
    error_seconds = float(os.getenv("CLIENT_FORWARD_ERROR_SECONDS", "5"))
    if idle_seconds < 0.5 or error_seconds < 1:
        raise RuntimeError("client forward polling intervals are too small")

    with httpx.Client(timeout=15.0) as client:
        while True:
            try:
                if not _send_one(
                    client,
                    api_key=api_key,
                    telegram_token=telegram_token,
                ):
                    time.sleep(idle_seconds)
            except Exception:
                logger.exception("CLIENT_FORWARD_FAILED")
                time.sleep(error_seconds)


if __name__ == "__main__":
    raise SystemExit(run())
