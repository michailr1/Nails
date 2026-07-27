from __future__ import annotations

import py_compile
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORWARD_DIR = ROOT / "ops" / "client_forward"
DEPLOY = ROOT / "ops" / "deploy" / "deploy.sh"


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
    subprocess.run(["bash", "-n", str(DEPLOY)], check=True)


def test_forward_service_preserves_trusted_token_boundary():
    service = (FORWARD_DIR / "nails-client-forward.service").read_text(
        encoding="utf-8"
    )
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


def test_forward_runtime_supports_explicit_desired_state():
    script = (FORWARD_DIR / "deploy_runtime.sh").read_text(encoding="utf-8")
    assert "NAILS_CLIENT_FORWARD_DESIRED_ACTIVE" in script
    assert '"preserve" || "$DESIRED_ACTIVE" == "true"' in script
    assert '"$desired" == "false"' in script
    assert "systemctl enable --now nails-client-forward.service" in script
    assert "systemctl disable --now nails-client-forward.service" in script


def test_permanent_deploy_owns_client_runtime_lifecycle():
    deploy = DEPLOY.read_text(encoding="utf-8")
    assert 'CLIENT_BOT_IMAGE="nails-nails-client-bot:latest"' in deploy
    assert "validate_client_runtime_config" in deploy
    assert (
        "CLIENT_API_ENABLED and CLIENT_BOT_ENABLED must be enabled together"
        in deploy
    )
    assert "client and trusted master Telegram bot tokens must differ" in deploy
    assert (
        'compose build --build-arg GIT_SHA="$RELEASE_SHA" '
        "nails-api nails-web nails-client-bot"
    ) in deploy
    assert 'bash "$WORKTREE/ops/client_forward/deploy_runtime.sh" snapshot' in deploy
    assert 'bash "$WORKTREE/ops/client_forward/deploy_runtime.sh" stop' in deploy
    assert 'bash "$WORKTREE/ops/client_forward/deploy_runtime.sh" install' in deploy
    assert 'bash "$WORKTREE/ops/client_forward/deploy_runtime.sh" restore' in deploy
    assert (
        "compose up -d --no-deps --force-recreate --no-build nails-client-bot"
        in deploy
    )
    assert "RUNNING_CLIENT_BOT_SHA" in deploy
    assert "CANDIDATE_DEPLOY_OK=true" in deploy


def test_permanent_deploy_never_prints_client_or_master_bot_token():
    deploy = DEPLOY.read_text(encoding="utf-8")
    assert 'printf %s "$CLIENT_TELEGRAM_BOT_TOKEN"' not in deploy
    assert 'printf %s "$TELEGRAM_BOT_TOKEN"' not in deploy
    assert "client_token=%s" not in deploy
    assert "master_token=%s" not in deploy
