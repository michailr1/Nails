from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = ROOT / "backend" / "app"
OPS = ROOT / "ops" / "client_bot"


def test_client_runtime_has_no_database_imports():
    sources = [
        BACKEND_APP / "client_bot_v1.py",
        BACKEND_APP / "client_bot_outbox.py",
        BACKEND_APP / "client_bot_booking_flow.py",
    ]
    forbidden = (
        "from app.db import",
        "import app.db",
        "from sqlalchemy",
        "import sqlalchemy",
    )
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in forbidden), path.name


def test_systemd_service_is_separate_and_uses_client_v1_entrypoint():
    unit = (OPS / "nails-client-bot.service").read_text(encoding="utf-8")
    assert "ExecStart=" in unit
    assert "-m app.client_bot_v1" in unit
    assert "EnvironmentFile=/opt/nails/.env" in unit
    assert "CLIENT_BOT_STATUS_PATH=/run/nails/client-bot-status.json" in unit
    assert "WorkingDirectory=/opt/nails/repo/backend" in unit
    assert "hermes-gateway" not in unit


def test_runtime_shell_scripts_and_systemd_unit_are_valid():
    for name in ("activate.sh", "deactivate.sh", "deploy_runtime.sh"):
        subprocess.run(["bash", "-n", str(OPS / name)], check=True)
    subprocess.run(
        ["systemd-analyze", "verify", str(OPS / "nails-client-bot.service")],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_activation_requires_separate_client_credentials_and_singleton_runtime():
    script = (OPS / "activate.sh").read_text(encoding="utf-8")
    assert "CLIENT_API_ENABLED must be true" in script
    assert "CLIENT_BOT_ENABLED must be true" in script
    assert "client and master internal keys must differ" in script
    assert "client and master Telegram tokens must differ" in script
    assert "CLIENT_TELEGRAM_BOT_TOKEN" in script
    assert "compose rm -sf nails-client-bot" in script
    assert "systemctl enable --now nails-client-bot.service" in script
    assert "CLIENT_RUNTIME_ACTIVATED=true" in script


def test_controlled_runtime_has_explicit_deactivation_path():
    script = (OPS / "deactivate.sh").read_text(encoding="utf-8")
    assert "CLIENT_API_ENABLED=false" in script
    assert "CLIENT_BOT_ENABLED=false" in script
    assert "systemctl disable --now nails-client-bot.service" in script
    assert "compose rm -sf nails-client-bot" in script
    assert "CLIENT_RUNTIME_DEACTIVATED=true" in script


def test_runtime_health_does_not_read_database_directly():
    health = (OPS / "health.py").read_text(encoding="utf-8")
    assert "/api/v1/client/notifications/internal/health" in health
    assert "sqlalchemy" not in health
    assert "DATABASE_URL" not in health


def test_repository_contains_no_real_client_bot_token():
    token_prefix = "bot" + "[0-9]"
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "CLIENT_TELEGRAM_BOT_TOKEN=" in env
    assert env.split("CLIENT_TELEGRAM_BOT_TOKEN=", 1)[1].splitlines()[0] == ""
    assert token_prefix not in env
