import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "ops" / "deploy" / "candidate_deploy.sh"
COMPOSE = ROOT / "compose.yaml"


def test_candidate_adapter_is_executable():
    assert ADAPTER.stat().st_mode & 0o111


def test_production_compose_defaults_are_preserved_and_parameterized():
    source = COMPOSE.read_text(encoding="utf-8")

    assert "name: ${NAILS_COMPOSE_PROJECT_NAME:-nails}" in source
    assert "name: ${NAILS_POSTGRES_VOLUME_NAME:-nails-postgres-data}" in source
    assert "name: ${NAILS_EDGE_NETWORK_NAME:-nails-edge}" in source
    assert "name: ${NAILS_INTERNAL_NETWORK_NAME:-nails-internal}" in source
    assert "${NAILS_API_PORT:-8210}:8000" in source
    assert "${NAILS_WEB_PORT:-8220}:8080" in source


def test_candidate_adapter_never_delegates_to_release_deploy():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "deploy.sh" not in source
    assert "systemctl" not in source
    assert "client_forward" not in source
    assert "gateway" not in source
    assert "nails-client-bot.service" not in source
    assert "compose up -d --build --wait nails-db nails-api nails-web" in source
    assert "nails-client-bot" in source
    assert "candidate client bot must not be created" in source


def test_candidate_adapter_requires_nonproduction_env_ports_and_database():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "NAILS_CANDIDATE_ENV is required" in source
    assert "candidate env must not be the production env" in source
    assert "candidate env must be a regular non-symlink file" in source
    assert "candidate env must not be accessible by group or others" in source
    assert "candidate API port must not be the production port" in source
    assert "candidate web port must not be the production port" in source
    assert "candidate DATABASE_URL must target the isolated nails-db service" in source
    assert "candidate DATABASE_URL must not target a host database" in source
    assert "candidate client bot must be disabled" in source
    assert "candidate Hermes access sync must be disabled" in source


def test_candidate_resources_are_derived_from_exact_sha():
    source = ADAPTER.read_text(encoding="utf-8")

    assert 'actual_sha="$(git -C "$REPO_ROOT" rev-parse HEAD)"' in source
    assert '[[ "$actual_sha" == "$SHA" ]]' in source
    assert 'suffix="${SHA:0:12}"' in source
    assert 'project="nails-candidate-${suffix}"' in source
    assert 'volume="${project}-postgres"' in source
    assert 'edge_network="${project}-edge"' in source
    assert 'internal_network="${project}-internal"' in source


def test_candidate_lifecycle_is_explicit_and_failure_cleans_only_candidate():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "NAILS_CANDIDATE_ACTION must be up, status, or down" in source
    assert "compose down --volumes --remove-orphans" in source
    assert "trap cleanup_failed_up EXIT" in source
    assert "candidate project already exists; run candidate down first" in source
    assert "candidate volume already exists; run candidate down first" in source
    assert "candidate_cleanup_ok=true" in source


def test_candidate_guards_production_container_set_and_volume():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "production_ids_before=" in source
    assert "production_volume_before=" in source
    assert "production container set changed during candidate action" in source
    assert "production database volume changed during candidate action" in source
    assert "production_runtime_unchanged=true" in source
    assert "production_db_unchanged=true" in source


def test_candidate_adapter_rejects_production_env_before_docker(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_marker = tmp_path / "docker-called"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        f"touch {docker_marker}\n"
        "exit 99\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o700)

    env = os.environ.copy()
    env.update(
        {
            "NAILS_CANDIDATE_ENV": "/opt/nails/.env",
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    result = subprocess.run(
        [str(ADAPTER), "0" * 40],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "candidate env must not be the production env" in result.stderr
    assert not docker_marker.exists()
