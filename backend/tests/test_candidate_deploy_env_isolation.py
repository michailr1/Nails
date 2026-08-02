import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "ops" / "deploy" / "candidate_deploy.sh"
DEPLOY = ROOT / "ops" / "deploy" / "deploy.sh"
FORWARD_TARGET = 'bash "$WORKTREE/ops/client_forward/deploy_runtime.sh"'
GUARD_TARGET = 'bash "$NAILS_CANDIDATE_CLIENT_FORWARD_GUARD"'


def test_candidate_adapter_is_executable():
    assert ADAPTER.stat().st_mode & 0o111


def test_candidate_adapter_preserves_production_default_and_requires_override():
    adapter = ADAPTER.read_text(encoding="utf-8")
    deploy = DEPLOY.read_text(encoding="utf-8")

    assert 'BACKEND_ENV="/opt/nails/.env"' in deploy
    assert "NAILS_CANDIDATE_ENV is required" in adapter
    assert "candidate env must not be the production env" in adapter
    assert "candidate env must be a regular non-symlink file" in adapter
    assert "candidate env must not be accessible by group or others" in adapter


def _source_forward_lines() -> list[str]:
    return [
        line
        for line in DEPLOY.read_text(encoding="utf-8").splitlines()
        if FORWARD_TARGET in line
    ]


def _install_fake_docker(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(mode=0o700)
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        "if [[ $1 == inspect && $2 == -f ]]; then\n"
        "  case $3 in\n"
        "    '{{.Id}}') printf 'candidate-test-client-bot-id\\n' ;;\n"
        "    '{{.State.Running}}') printf 'true\\n' ;;\n"
        "    *) exit 2 ;;\n"
        "  esac\n"
        "  exit 0\n"
        "fi\n"
        "printf 'unexpected fake docker invocation: %s\\n' \"$*\" >&2\n"
        "exit 2\n",
        encoding="utf-8",
    )
    docker.chmod(0o700)
    return fake_bin


def _render_adapter(tmp_path: Path) -> tuple[str, Path]:
    candidate_env = tmp_path / "candidate.env"
    candidate_env.write_text(
        "CLIENT_API_ENABLED=false\nCLIENT_BOT_ENABLED=false\n",
        encoding="utf-8",
    )
    candidate_env.chmod(0o600)

    render_dir = tmp_path / "render"
    render_dir.mkdir(mode=0o700)
    fake_bin = _install_fake_docker(tmp_path)

    env = os.environ.copy()
    env.update(
        {
            "NAILS_CANDIDATE_ENV": str(candidate_env),
            "NAILS_CANDIDATE_RENDER_DIR": str(render_dir),
            "NAILS_CANDIDATE_TMP_ROOT": str(tmp_path),
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    result = subprocess.run(
        [str(ADAPTER), "0" * 40],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout, render_dir


def test_candidate_adapter_renders_every_actual_forward_invocation(tmp_path):
    output, render_dir = _render_adapter(tmp_path)
    source_lines = _source_forward_lines()
    runtime = (render_dir / "runtime.sh").read_text(encoding="utf-8")

    assert source_lines
    assert "candidate_render_only=true" in output
    assert runtime.count(GUARD_TARGET) == len(source_lines)
    assert FORWARD_TARGET not in runtime

    for source_line in source_lines:
        expected = source_line.replace(FORWARD_TARGET, GUARD_TARGET, 1)
        assert expected in runtime.splitlines()


def test_candidate_forward_guard_supports_every_action_used_by_deploy(tmp_path):
    _, render_dir = _render_adapter(tmp_path)
    guard = render_dir / "client-forward-guard.sh"

    fake_worktree = tmp_path / "worktree"
    fake_forward = fake_worktree / "ops" / "client_forward"
    fake_forward.mkdir(parents=True)
    fake_runtime = fake_forward / "deploy_runtime.sh"
    fake_runtime.write_text(
        "#!/usr/bin/env bash\nprintf 'delegated_action=%s\\n' \"$1\"\n",
        encoding="utf-8",
    )
    fake_runtime.chmod(0o700)

    actions = set()
    for line in _source_forward_lines():
        suffix = line.split(FORWARD_TARGET, 1)[1].strip()
        actions.add(shlex.split(suffix)[0])

    assert actions
    for action in actions:
        env = os.environ.copy()
        env["NAILS_DEPLOY_WORKTREE"] = str(fake_worktree)
        result = subprocess.run(
            [str(guard), action, str(tmp_path / "backup"), "origin/pr/257"],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        if action == "snapshot":
            assert "delegated_action=snapshot" in result.stdout
        else:
            assert f"candidate_client_forward_{action}_skipped=true" in result.stdout


def test_candidate_adapter_keeps_fail_closed_contract_checks():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "deploy.sh BACKEND_ENV contract changed; adapter requires review" in source
    assert "deploy.sh client-forward invocation contract changed; adapter requires review" in source
    assert (
        "deploy.sh client-forward disabled assertion contract changed; "
        "adapter requires review"
    ) in source
    assert "failed to guard every client-forward invocation" in source
    assert "unguarded client-forward invocation remains" in source
    assert "production Compose client-bot container ID changed" in source
    assert "failed to guard every client-bot stop" in source
    assert "failed to guard every client-bot recreate" in source
    assert "failed to guard every client-bot removal" in source
    assert "unguarded client-bot stop remains" in source
    assert "unguarded client-bot recreate remains" in source
    assert "unguarded client-bot removal remains" in source


def test_candidate_adapter_cleans_temporary_files_and_propagates_status():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "trap cleanup EXIT" in source
    assert 'rm -f -- "$runtime_script" "$forward_guard"' in source
    assert 'NAILS_CANDIDATE_ENV="$CANDIDATE_ENV"' in source
    assert 'NAILS_CANDIDATE_CLIENT_FORWARD_GUARD="$forward_guard"' in source
    assert 'bash "$runtime_script" "$1"' in source
    assert "status=$?" in source
    assert 'exit "$status"' in source
