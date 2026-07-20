#!/usr/bin/env python3
"""Idempotently add the Nails master portal to the Telegram bot command menu."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROFILE_ENV = Path("/root/.hermes/profiles/nails/.env")
BOT_API_BASE = "https://api.telegram.org"
PORTAL_COMMAND = {
    "command": "portal",
    "description": "Личный кабинет мастера",
}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def merge_commands(existing: list[dict[str, Any]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    portal_written = False
    for item in existing:
        command = str(item.get("command", "")).strip().lstrip("/")
        description = str(item.get("description", "")).strip()
        if not command or not description:
            continue
        if command == PORTAL_COMMAND["command"]:
            if not portal_written:
                merged.append(PORTAL_COMMAND.copy())
                portal_written = True
            continue
        merged.append({"command": command, "description": description})
    if not portal_written:
        merged.append(PORTAL_COMMAND.copy())
    return merged


def telegram_call(token: str, method: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"{BOT_API_BASE}/bot{token}/{method}"
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Telegram Bot API request failed for {method}") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram Bot API rejected {method}")
    return result.get("result")


def main() -> int:
    if not PROFILE_ENV.is_file():
        print("TELEGRAM_MENU_OK=false error=profile_env_missing", file=sys.stderr)
        return 1

    env = parse_env(PROFILE_ENV)
    token = env.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_MENU_OK=false error=telegram_token_missing", file=sys.stderr)
        return 1

    existing = telegram_call(token, "getMyCommands")
    if not isinstance(existing, list):
        print("TELEGRAM_MENU_OK=false error=invalid_commands_response", file=sys.stderr)
        return 1

    commands = merge_commands(existing)
    telegram_call(token, "setMyCommands", {"commands": commands})
    verified = telegram_call(token, "getMyCommands")
    if not isinstance(verified, list) or PORTAL_COMMAND not in verified:
        print("TELEGRAM_MENU_OK=false error=portal_command_not_verified", file=sys.stderr)
        return 1

    preserved = sum(1 for command in commands if command["command"] != "portal")
    print(f"TELEGRAM_MENU_OK=true portal_command=true preserved_commands={preserved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
