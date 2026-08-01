from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "ops" / "deploy" / "candidate_deploy.sh"
DEPLOY = ROOT / "ops" / "deploy" / "deploy.sh"


def test_candidate_adapter_preserves_production_default_and_requires_override():
    adapter = ADAPTER.read_text(encoding="utf-8")
    deploy = DEPLOY.read_text(encoding="utf-8")

    assert 'BACKEND_ENV="/opt/nails/.env"' in deploy
    assert 'NAILS_CANDIDATE_ENV is required' in adapter
    assert 'candidate env must not be the production env' in adapter
    assert 'candidate env must be a regular non-symlink file' in adapter
    assert 'candidate env must not be accessible by group or others' in adapter


def test_candidate_adapter_changes_exactly_the_backend_env_assignment():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "grep -Fxc \"$assignment\"" in source
    assert 'BACKEND_ENV="${NAILS_CANDIDATE_ENV:-/opt/nails/.env}"' in source
    assert "awk -v replacement=" in source
    assert "deploy.sh BACKEND_ENV contract changed; adapter requires review" in source


def test_candidate_adapter_cleans_temporary_script_and_propagates_status():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "trap cleanup EXIT" in source
    assert 'rm -f -- "$runtime_script"' in source
    assert 'NAILS_CANDIDATE_ENV="$CANDIDATE_ENV" bash "$runtime_script" "$1"' in source
    assert "status=$?" in source
    assert 'exit "$status"' in source
