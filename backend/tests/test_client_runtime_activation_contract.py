from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTIVATE = ROOT / "ops" / "client_runtime" / "activate.sh"


def test_activation_script_is_valid_bash():
    subprocess.run(["bash", "-n", str(ACTIVATE)], check=True)


def test_activation_requires_separate_client_credentials_and_clean_main():
    text = ACTIVATE.read_text(encoding="utf-8")
    assert 'branch --show-current)' in text
    assert 'production_tree_dirty' in text
    assert 'CLIENT_API_ENABLED' in text
    assert 'CLIENT_BOT_ENABLED' in text
    assert 'CLIENT_INTERNAL_API_KEY' in text
    assert 'CLIENT_TELEGRAM_BOT_TOKEN' in text
    assert 'HERMES_ENV="/root/.hermes/profiles/nails/.env"' in text
    assert 'master_bot_token_missing' in text
    assert 'client_and_master_bot_tokens_must_differ' in text


def test_activation_uses_release_compose_and_trusted_forward_installer():
    text = ACTIVATE.read_text(encoding="utf-8")
    assert '--env-file "$ENV_FILE" build nails-client-bot' in text
    assert '--env-file "$ENV_FILE" up -d --no-deps --force-recreate nails-client-bot' in text
    assert 'ops/client_forward/deploy_runtime.sh' in text
    assert 'snapshot "$RUNTIME_BACKUP"' in text
    assert 'restore "$RUNTIME_BACKUP"' in text
    assert 'install "$RUNTIME_BACKUP"' in text
    assert 'CLIENT_RUNTIME_ACTIVATION_OK=true' in text
    assert 'CLIENT_RUNTIME_ACTIVATION_OK=false' in text


def test_activation_never_prints_or_passes_bot_tokens_as_cli_arguments():
    text = ACTIVATE.read_text(encoding="utf-8")
    assert 'printf %s "$CLIENT_TELEGRAM_BOT_TOKEN"' not in text
    assert '--token' not in text
    assert 'bot_token=%s' not in text
