from __future__ import annotations

from pathlib import Path
from typing import Any

from app.client_bot_outbox import (
    ClientBotRuntimeState,
    NotificationDrainer,
    OutboxRuntimeConfig,
)

ROOT = Path(__file__).resolve().parents[2]


class _Telegram:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, **payload: Any) -> None:
        self.calls.append((method, payload))


class _NotificationApi:
    def __init__(self) -> None:
        self.acks: list[tuple[str, str, str | None]] = []

    def ack(
        self,
        claim_id: str,
        outcome: str,
        error_code: str | None = None,
    ) -> None:
        self.acks.append((claim_id, outcome, error_code))


def test_docker_compose_is_the_only_client_bot_launch_mechanism():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    deploy = (ROOT / "ops" / "deploy" / "deploy.sh").read_text(encoding="utf-8")

    assert "exec python -m app.client_bot_v1" in compose
    assert "app.client_bot_runtime" not in compose
    assert "CLIENT_BOT_STATUS_PATH: /tmp/client-bot-status.json" in compose

    forbidden_paths = [
        ROOT / "backend" / "app" / "client_bot_runtime.py",
        ROOT / "ops" / "client_bot" / "activate.sh",
        ROOT / "ops" / "client_bot" / "deactivate.sh",
        ROOT / "ops" / "client_bot" / "deploy_runtime.sh",
        ROOT / "ops" / "client_bot" / "health.py",
        ROOT / "ops" / "client_bot" / "nails-client-bot.service",
    ]
    assert not [str(path.relative_to(ROOT)) for path in forbidden_paths if path.exists()]

    assert "remove_legacy_client_bot_runtime" in deploy
    assert 'systemctl disable --now "$LEGACY_CLIENT_BOT_SERVICE"' in deploy
    assert 'rm -f "$LEGACY_CLIENT_BOT_UNIT" "$LEGACY_CLIENT_BOT_STATUS"' in deploy
    assert "verify_client_bot_singleton" in deploy
    assert "expected exactly one client bot container" in deploy
    assert "app.client_bot_v1" in deploy
    assert "app.client_bot_runtime" in deploy  # forbidden process detection only
    assert "client_bot_singleton=%s" in deploy


def test_legacy_runtime_removal_returns_success_when_unit_is_absent():
    deploy = (ROOT / "ops" / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    function = deploy.split("remove_legacy_client_bot_runtime() {", 1)[1].split(
        "\n}\n\nverify_client_bot_singleton()",
        1,
    )[0]

    assert 'if systemctl is-active --quiet "$LEGACY_CLIENT_BOT_SERVICE"; then' in function
    assert 'if systemctl is-enabled --quiet "$LEGACY_CLIENT_BOT_SERVICE"; then' in function
    assert function.rstrip().endswith("return 0")
    assert 'systemctl is-enabled --quiet "$LEGACY_CLIENT_BOT_SERVICE" &&' not in function


def test_candidate_adapter_restores_preexisting_legacy_unit_state():
    adapter = (ROOT / "ops" / "deploy" / "candidate_deploy.sh").read_text(
        encoding="utf-8"
    )

    assert "production_legacy_client_bot_unit_snapshotted=true" in adapter
    assert "restore_legacy_client_bot_unit" in adapter
    assert 'cp -a "$legacy_unit_backup" "$legacy_unit"' in adapter
    assert "systemctl enable nails-client-bot.service" in adapter
    assert "systemctl start nails-client-bot.service" in adapter
    assert "production_legacy_client_bot_unit_restored=true" in adapter


def test_one_claim_is_sent_once_and_acked_once(tmp_path: Path):
    telegram = _Telegram()
    api = _NotificationApi()
    config = OutboxRuntimeConfig(
        client_api_url="http://nails-api",
        client_api_key="k" * 64,
        status_path=tmp_path / "client-bot-status.json",
        drain_interval_seconds=0.1,
        per_chat_interval_seconds=0.05,
    )
    state = ClientBotRuntimeState()
    drainer = NotificationDrainer(telegram, api, config, state)

    drainer._deliver(
        {
            "claimed": True,
            "claim_id": "11111111-1111-4111-8111-111111111111",
            "telegram_user_id": 900001,
            "event_type": "approved",
            "payload": {
                "service_name": "Маникюр",
                "starts_at": "2026-08-02T12:00:00+03:00",
            },
        }
    )

    assert telegram.calls == [
        (
            "sendMessage",
            {
                "chat_id": 900001,
                "text": "Запись подтверждена ✅\nМаникюр\n02.08 в 11:00",
            },
        )
    ]
    assert api.acks == [
        ("11111111-1111-4111-8111-111111111111", "sent", None)
    ]
    assert state.sent_count == 1
