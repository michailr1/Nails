from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

STATUS_PATH = Path(os.getenv("CLIENT_BOT_STATUS_PATH", "/run/nails/client-bot-status.json"))
API_URL = os.getenv("NAILS_CLIENT_API_URL", "http://127.0.0.1:8210").rstrip("/")
API_KEY = os.getenv("CLIENT_INTERNAL_API_KEY", "").strip()
MAX_POLL_AGE_SECONDS = int(os.getenv("CLIENT_BOT_MAX_POLL_AGE_SECONDS", "90"))


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def main() -> int:
    if len(API_KEY) < 32:
        print("CLIENT_BOT_HEALTH_OK=false reason=client_internal_key_missing")
        return 2
    if not STATUS_PATH.is_file():
        print("CLIENT_BOT_HEALTH_OK=false reason=status_file_missing")
        return 1

    runtime = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    last_poll = _parse_time(runtime.get("last_poll_at"))
    if last_poll is None:
        print("CLIENT_BOT_HEALTH_OK=false reason=no_successful_poll")
        return 1
    poll_age = int((datetime.now(UTC) - last_poll).total_seconds())
    if poll_age > MAX_POLL_AGE_SECONDS:
        print(
            "CLIENT_BOT_HEALTH_OK=false "
            f"reason=poll_stale last_poll_age_seconds={poll_age}"
        )
        return 1

    response = httpx.get(
        f"{API_URL}/api/v1/client/notifications/internal/health",
        headers={"X-Nails-Client-Internal-Key": API_KEY},
        timeout=10.0,
    )
    response.raise_for_status()
    queue = response.json()
    print(
        "CLIENT_BOT_HEALTH_OK=true "
        f"last_poll_age_seconds={poll_age} "
        f"sent_count={int(runtime.get('sent_count') or 0)} "
        f"retry_count={int(runtime.get('retry_count') or 0)} "
        f"unreachable_count={int(runtime.get('unreachable_count') or 0)} "
        f"runtime_failed_count={int(runtime.get('failed_count') or 0)} "
        f"pending_count={int(queue.get('pending_count') or 0)} "
        f"claimed_count={int(queue.get('claimed_count') or 0)} "
        f"failed_count={int(queue.get('failed_count') or 0)} "
        f"oldest_pending_age_seconds={queue.get('oldest_pending_age_seconds')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
