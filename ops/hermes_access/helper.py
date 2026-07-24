from __future__ import annotations

import fcntl
import json
import os
import shutil
import socketserver
import stat
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

ENV_PATH = Path("/root/.hermes/profiles/nails/.env")
SOCKET_PATH = Path("/run/nails-hermes-access/access.sock")
LOCK_PATH = Path("/run/lock/nails-hermes-access.lock")
GATEWAY = "hermes-gateway-nails.service"
USER_RUNTIME_DIR = "/run/user/0"
PARAMETER = "TELEGRAM_ALLOWED_USERS"


def _systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = USER_RUNTIME_DIR
    env["HOME"] = "/root"
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _parse_allowed(raw: str) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for item in raw.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        value = int(candidate)
        if value <= 0:
            raise ValueError("invalid_allowlist_value")
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _render_env(original: str, allowed: list[int]) -> str:
    lines = original.splitlines(keepends=True)
    replacement = f"{PARAMETER}={','.join(str(value) for value in allowed)}\n"
    found = False
    rendered: list[str] = []
    for line in lines:
        if line.startswith(f"{PARAMETER}="):
            if not found:
                rendered.append(replacement)
                found = True
            continue
        rendered.append(line)
    if not found:
        if rendered and not rendered[-1].endswith("\n"):
            rendered[-1] += "\n"
        rendered.append(replacement)
    return "".join(rendered)


def _read_state() -> tuple[str, list[int], os.stat_result]:
    original = ENV_PATH.read_text(encoding="utf-8")
    metadata = ENV_PATH.stat()
    value = ""
    for line in original.splitlines():
        if line.startswith(f"{PARAMETER}="):
            value = line.split("=", 1)[1]
            break
    return original, _parse_allowed(value), metadata


def _atomic_write(content: str, metadata: os.stat_result) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".env.nails-access-", dir=ENV_PATH.parent)
    path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(path, stat.S_IMODE(metadata.st_mode))
        os.chown(path, metadata.st_uid, metadata.st_gid)
        os.replace(path, ENV_PATH)
        directory_fd = os.open(ENV_PATH.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        path.unlink(missing_ok=True)


def _reload_and_verify(telegram_user_id: int, expected_allowed: bool) -> None:
    reloaded = _systemctl("reload", GATEWAY)
    if reloaded.returncode != 0:
        raise RuntimeError("gateway_reload_failed")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        active = _systemctl("is-active", "--quiet", GATEWAY)
        if active.returncode == 0:
            _, allowed, _ = _read_state()
            if (telegram_user_id in allowed) is expected_allowed:
                return
        time.sleep(0.5)
    raise RuntimeError("gateway_verification_failed")


def mutate(action: str, telegram_user_id: int) -> dict[str, Any]:
    if action not in {"grant", "revoke"}:
        raise ValueError("unsupported_action")
    if telegram_user_id <= 0:
        raise ValueError("invalid_telegram_user_id")

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        original, allowed, metadata = _read_state()
        before = telegram_user_id in allowed
        if action == "grant" and not before:
            allowed.append(telegram_user_id)
        elif action == "revoke" and before:
            allowed = [value for value in allowed if value != telegram_user_id]
        expected = action == "grant"
        changed = before is not expected
        if not changed:
            return {"changed": False, "allowed": expected}

        rendered = _render_env(original, allowed)
        backup = ENV_PATH.parent / f".env.nails-access-backup-{os.getpid()}"
        shutil.copy2(ENV_PATH, backup)
        try:
            _atomic_write(rendered, metadata)
            _reload_and_verify(telegram_user_id, expected)
        except Exception:
            backup_metadata = backup.stat()
            _atomic_write(backup.read_text(encoding="utf-8"), backup_metadata)
            _systemctl("reload", GATEWAY)
            raise
        finally:
            backup.unlink(missing_ok=True)
        return {"changed": True, "allowed": expected}


def status() -> dict[str, Any]:
    _, allowed, _ = _read_state()
    active = _systemctl("is-active", "--quiet", GATEWAY).returncode == 0
    return {"active": active, "allowed_user_count": len(allowed)}


class Handler(BaseHTTPRequestHandler):
    server_version = "nails-hermes-access/1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/v1/access/status":
            self._write(404, {"code": "not_found"})
            return
        try:
            self._write(200, status())
        except Exception:
            self._write(503, {"code": "status_failed"})

    def do_POST(self) -> None:
        if self.path not in {"/v1/access/grant", "/v1/access/revoke"}:
            self._write(404, {"code": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1024:
                raise ValueError("invalid_body")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if set(payload) != {"telegram_user_id"}:
                raise ValueError("invalid_body")
            telegram_user_id = int(payload["telegram_user_id"])
            action = self.path.rsplit("/", 1)[-1]
            self._write(200, mutate(action, telegram_user_id))
        except (ValueError, TypeError, json.JSONDecodeError):
            self._write(400, {"code": "invalid_request"})
        except Exception:
            self._write(503, {"code": "hermes_access_apply_failed"})


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main() -> None:
    if not ENV_PATH.is_file():
        raise SystemExit("Hermes profile .env is missing")
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOCKET_PATH.unlink(missing_ok=True)
    with Server(str(SOCKET_PATH), Handler) as server:
        os.chmod(SOCKET_PATH, 0o660)
        gid = int(os.environ.get("NAILS_HERMES_ACCESS_GID", "42891"))
        os.chown(SOCKET_PATH, 0, gid)
        server.serve_forever()


if __name__ == "__main__":
    main()
