from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "ops" / "deploy" / "candidate_deploy.sh"
DEPLOY = ROOT / "ops" / "deploy" / "deploy.sh"


def test_candidate_adapter_is_executable():
    assert ADAPTER.stat().st_mode & 0o111


def test_candidate_adapter_preserves_production_default_and_requires_override():
    adapter = ADAPTER.read_text(encoding="utf-8")
    deploy = DEPLOY.read_text(encoding="utf-8")

    assert 'BACKEND_ENV="/opt/nails/.env"' in deploy
    assert 'NAILS_CANDIDATE_ENV is required' in adapter
    assert 'candidate env must not be the production env' in adapter
    assert 'candidate env must be a regular non-symlink file' in adapter
    assert 'candidate env must not be accessible by group or others' in adapter


def test_candidate_adapter_guards_exact_normative_contract():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "grep -Fxc \"$assignment\"" in source
    assert 'BACKEND_ENV="${NAILS_CANDIDATE_ENV:-/opt/nails/.env}"' in source
    assert "deploy.sh BACKEND_ENV contract changed; adapter requires review" in source

    assert 'client_forward_invocation=' in source
    assert '"$(grep -Fxc "$client_forward_invocation" "$DEPLOY_SCRIPT")" -eq 4' in source
    assert "deploy.sh client-forward invocation contract changed; adapter requires review" in source
    assert 'client_forward_disabled_assertion=' in source
    assert "deploy.sh client-forward disabled assertion contract changed; adapter requires review" in source


def test_candidate_adapter_delegates_snapshot_but_skips_mutations():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "case \"$action\" in" in source
    assert "snapshot)" in source
    assert 'exec bash "${NAILS_DEPLOY_WORKTREE}/ops/client_forward/deploy_runtime.sh" "$@"' in source
    assert "stop|install|restore)" in source
    assert "candidate_client_forward_%s_skipped=true" in source
    assert 'bash "$NAILS_CANDIDATE_CLIENT_FORWARD_GUARD"' in source
    assert "candidate_client_forward_preserved=true" in source
    assert "production_client_forward_guarded=true" in source


def test_candidate_adapter_cleans_temporary_files_and_propagates_status():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "trap cleanup EXIT" in source
    assert 'rm -f -- "$runtime_script" "$client_forward_guard"' in source
    assert 'NAILS_CANDIDATE_ENV="$CANDIDATE_ENV"' in source
    assert 'NAILS_CANDIDATE_CLIENT_FORWARD_GUARD="$client_forward_guard"' in source
    assert 'bash "$runtime_script" "$1"' in source
    assert "status=$?" in source
    assert 'exit "$status"' in source
