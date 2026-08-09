from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_ADAPTER = REPO_ROOT / "ops" / "deploy" / "candidate_deploy.sh"
COMPOSE_FILE = REPO_ROOT / "compose.yaml"
POSTGRES_INIT_SCRIPT = REPO_ROOT / "deployment" / "postgres" / "init-app-user.sh"


def _git_mode(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT)
    output = subprocess.check_output(
        ["git", "ls-files", "-s", "--", str(relative)],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    assert output, f"tracked file not found: {relative}"
    return output.split(maxsplit=1)[0]


def test_candidate_adapter_uses_isolated_names_and_ports():
    source = CANDIDATE_ADAPTER.read_text(encoding="utf-8")

    assert "NAILS_CANDIDATE_ENV" in source
    assert "NAILS_CANDIDATE_API_PORT" in source
    assert "NAILS_CANDIDATE_WEB_PORT" in source
    assert "NAILS_COMPOSE_PROJECT_NAME" in source
    assert "NAILS_POSTGRES_VOLUME_NAME" in source
    assert "NAILS_EDGE_NETWORK_NAME" in source
    assert "NAILS_INTERNAL_NETWORK_NAME" in source
    assert "NAILS_API_BIND" in source
    assert "NAILS_WEB_BIND" in source
    assert '"nails-db" "nails-api" "nails-web"' in source
    assert '"nails-client-bot"' not in re.search(
        r"CANDIDATE_SERVICES=\((.*?)\)", source, re.DOTALL
    ).group(1)


def test_candidate_adapter_rejects_production_database_or_ports():
    source = CANDIDATE_ADAPTER.read_text(encoding="utf-8")

    assert 'candidate_require "DATABASE_URL"' in source
    assert 'candidate_require "POSTGRES_DB"' in source
    assert 'candidate_require "POSTGRES_ADMIN_USER"' in source
    assert 'candidate_require "POSTGRES_ADMIN_PASSWORD"' in source
    assert 'candidate_require "APP_DB_USER"' in source
    assert 'candidate_require "APP_DB_PASSWORD"' in source
    assert 'candidate_require "NAILS_API_PORT"' in source
    assert 'candidate_require "NAILS_WEB_PORT"' in source
    assert 'candidate_require_false "CLIENT_BOT_ENABLED"' in source
    assert 'candidate_require_false "HERMES_ACCESS_SYNC_ENABLED"' in source
    assert 'require_nonproduction_port "NAILS_API_PORT"' in source
    assert 'require_nonproduction_port "NAILS_WEB_PORT"' in source
    assert 'candidate_value "DATABASE_URL"' in source
    assert 'candidate database url must target nails-db service' in source
    assert 'candidate database url must not target production host paths' in source


def test_candidate_adapter_checks_production_invariance():
    source = CANDIDATE_ADAPTER.read_text(encoding="utf-8")

    required_markers = (
        "capture_production_baseline",
        "assert_production_unchanged",
        "PRODUCTION_CHECKOUT_SHA",
        "PRODUCTION_STATUS",
        "PRODUCTION_API_ID",
        "PRODUCTION_WEB_ID",
        "PRODUCTION_DB_ID",
        "PRODUCTION_DB_VOLUME_ID",
        "PRODUCTION_ENV_HASH",
        "production checkout changed",
        "production working tree changed",
        "production api container changed",
        "production web container changed",
        "production db container changed",
        "production db volume changed",
        "production environment changed",
    )
    for marker in required_markers:
        assert marker in source


def test_candidate_compose_can_name_database_volume_and_networks():
    source = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "${NAILS_COMPOSE_PROJECT_NAME:-nails}" in source
    assert "${NAILS_POSTGRES_VOLUME_NAME:-nails-postgres-data}" in source
    assert "${NAILS_EDGE_NETWORK_NAME:-nails-edge}" in source
    assert "${NAILS_INTERNAL_NETWORK_NAME:-nails-internal}" in source
    assert '"${NAILS_API_BIND:-127.0.0.1}:${NAILS_API_PORT:-8210}:8000"' in source
    assert '"${NAILS_WEB_BIND:-127.0.0.1}:${NAILS_WEB_PORT:-8220}:8080"' in source


def test_fresh_postgres_init_script_is_executable_from_git():
    assert POSTGRES_INIT_SCRIPT.read_text(encoding="utf-8").startswith("#!/bin/sh\n")
    assert _git_mode(POSTGRES_INIT_SCRIPT) == "100755"
