from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_passes_git_sha_to_every_built_runtime():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert compose.count("GIT_SHA: ${GIT_SHA:-unknown}") == 3
    assert "ARG GIT_SHA=unknown" in (ROOT / "backend/Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "ARG GIT_SHA=unknown" in (ROOT / "web/Dockerfile").read_text(
        encoding="utf-8"
    )


def test_candidate_adapter_injects_and_proves_exact_runtime_sha():
    adapter = (ROOT / "ops/deploy/candidate_deploy.sh").read_text(encoding="utf-8")

    assert 'GIT_SHA="$SHA" \\' in adapter
    assert "candidate_api_sha=" in adapter
    assert "candidate_web_sha=" in adapter
    assert '[[ "$candidate_api_sha" == "$SHA" ]]' in adapter
    assert '[[ "$candidate_web_sha" == "$SHA" ]]' in adapter
    assert "candidate API runtime SHA" in adapter
    assert "candidate WEB runtime SHA" in adapter
    assert "candidate_runtime_api_sha=%s" in adapter
    assert "candidate_runtime_web_sha=%s" in adapter
    assert adapter.index('[[ "$candidate_api_sha" == "$SHA" ]]') < adapter.index(
        "CANDIDATE_RUNTIME_OK=true"
    )
    assert adapter.index('[[ "$candidate_web_sha" == "$SHA" ]]') < adapter.index(
        "CANDIDATE_RUNTIME_OK=true"
    )
