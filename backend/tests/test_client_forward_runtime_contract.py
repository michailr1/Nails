from __future__ import annotations

import py_compile
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORWARD_DIR = ROOT / "ops" / "client_forward"


def test_forward_sender_python_compiles():
    py_compile.compile(
        str(FORWARD_DIR / "send.py"),
        doraise=True,
    )


def test_forward_runtime_shell_is_syntactically_valid():
    subprocess.run(
        ["bash", "-n", str(FORWARD_DIR / "deploy_runtime.sh")],
        check=True,
    )


def test_forward_service_preserves_trusted_token_boundary():
    service = (FORWARD_DIR / "nails-client-forward.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=/opt/nails/.env" in service
    assert "EnvironmentFile=-/root/.hermes/profiles/nails/.env" in service
    assert "ExecStart=" in service and "/opt/nails/client-forward/send.py" in service
    assert "NoNewPrivileges=true" in service
    assert "ProtectSystem=strict" in service
    assert "CLIENT_TELEGRAM_BOT_TOKEN" not in service


def test_forward_sender_uses_internal_api_and_master_bot_token_only():
    sender = (FORWARD_DIR / "send.py").read_text(encoding="utf-8")
    assert '"X-Nails-Internal-Key"' in sender
    assert '"X-Nails-Client-Internal-Key"' not in sender
    assert 'os.getenv("TELEGRAM_BOT_TOKEN"' in sender
    assert "CLIENT_TELEGRAM_BOT_TOKEN" not in sender
    assert "/api/v1/client/contact-forward/internal/claim" in sender
    assert "/api/v1/client/contact-forward/internal/ack" in sender
