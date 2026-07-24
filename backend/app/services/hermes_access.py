from __future__ import annotations

import http.client
import json
import socket
from dataclasses import dataclass
from typing import Any

from app.config import get_settings


class HermesAccessError(RuntimeError):
    pass


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float) -> None:
        super().__init__(host="localhost", timeout=timeout)
        self._socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._socket_path)
        self.sock = sock


@dataclass(frozen=True, slots=True)
class HermesAccessResult:
    changed: bool
    allowed: bool


class HermesAccessClient:
    def __init__(self, *, socket_path: str, timeout_seconds: float, enabled: bool) -> None:
        self._socket_path = socket_path
        self._timeout_seconds = timeout_seconds
        self._enabled = enabled

    def grant(self, telegram_user_id: int) -> HermesAccessResult:
        return self._mutate("grant", telegram_user_id)

    def revoke(self, telegram_user_id: int) -> HermesAccessResult:
        return self._mutate("revoke", telegram_user_id)

    def _mutate(self, action: str, telegram_user_id: int) -> HermesAccessResult:
        if not self._enabled:
            return HermesAccessResult(changed=False, allowed=action == "grant")
        payload = json.dumps({"telegram_user_id": telegram_user_id}).encode("utf-8")
        response = self._request(
            "POST",
            f"/v1/access/{action}",
            body=payload,
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        return HermesAccessResult(
            changed=bool(response.get("changed")),
            allowed=bool(response.get("allowed")),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        connection = _UnixHTTPConnection(self._socket_path, self._timeout_seconds)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            raw = response.read()
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            raise HermesAccessError("hermes_access_unavailable") from exc
        finally:
            connection.close()
        try:
            decoded = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HermesAccessError("hermes_access_invalid_response") from exc
        if response.status >= 400:
            code = decoded.get("code") if isinstance(decoded, dict) else None
            raise HermesAccessError(str(code or "hermes_access_failed"))
        if not isinstance(decoded, dict):
            raise HermesAccessError("hermes_access_invalid_response")
        return decoded


def get_hermes_access_client() -> HermesAccessClient:
    settings = get_settings()
    return HermesAccessClient(
        socket_path=settings.hermes_access_socket,
        timeout_seconds=settings.hermes_access_timeout_seconds,
        enabled=settings.hermes_access_sync_enabled,
    )
