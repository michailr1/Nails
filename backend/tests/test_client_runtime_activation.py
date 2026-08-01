from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = ROOT / "backend" / "app"


def test_client_runtime_has_no_database_imports():
    sources = [
        BACKEND_APP / "client_bot_v1.py",
        BACKEND_APP / "client_bot_outbox.py",
        BACKEND_APP / "client_bot_runtime_api.py",
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


def test_client_runtime_uses_only_the_compose_v1_entrypoint():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    deploy = (ROOT / "ops" / "deploy" / "deploy.sh").read_text(encoding="utf-8")

    assert "exec python -m app.client_bot_v1" in compose
    assert "app.client_bot_runtime" not in compose
    assert "CLIENT_BOT_STATUS_PATH: /tmp/client-bot-status.json" in compose
    assert "verify_client_bot_singleton" in deploy
    assert "remove_legacy_client_bot_runtime" in deploy


def test_host_client_runtime_path_is_absent():
    forbidden_paths = [
        ROOT / "backend" / "app" / "client_bot_runtime.py",
        ROOT / "ops" / "client_bot" / "activate.sh",
        ROOT / "ops" / "client_bot" / "deactivate.sh",
        ROOT / "ops" / "client_bot" / "deploy_runtime.sh",
        ROOT / "ops" / "client_bot" / "health.py",
        ROOT / "ops" / "client_bot" / "nails-client-bot.service",
    ]
    assert not [str(path.relative_to(ROOT)) for path in forbidden_paths if path.exists()]


def test_repository_contains_no_real_client_bot_token():
    token_prefix = "bot" + "[0-9]"
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "CLIENT_TELEGRAM_BOT_TOKEN=" in env
    assert env.split("CLIENT_TELEGRAM_BOT_TOKEN=", 1)[1].splitlines()[0] == ""
    assert token_prefix not in env
