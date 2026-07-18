from __future__ import annotations

from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def test_web_edge_contract() -> None:
    compose = _read("compose.yaml")
    nginx = _read("web/nginx.conf")
    dockerfile = _read("web/Dockerfile")

    expected_fragments = (
        '${NAILS_API_BIND:-127.0.0.1}:${NAILS_API_PORT:-8210}:8000',
        '${NAILS_WEB_BIND:-127.0.0.1}:${NAILS_WEB_PORT:-8220}:8080',
        "WEB_AUTH_ENABLED: ${WEB_AUTH_ENABLED:-false}",
        "WEB_AUTH_HMAC_KEY: ${WEB_AUTH_HMAC_KEY:-}",
        "nails-web:",
    )
    for fragment in expected_fragments:
        assert fragment in compose

    assert "location ^~ /web/api/auth/" in nginx
    assert "location ^~ /web/api/" in nginx
    assert "proxy_pass http://nails-api:8000;" in nginx
    assert "/api/v1/" not in nginx
    assert "client_max_body_size 16k;" in nginx
    assert "limit_req zone=web_auth" in nginx
    assert "frame-ancestors 'none'" in nginx

    assert dockerfile.startswith("FROM nginxinc/nginx-unprivileged:")
    assert "EXPOSE 8080" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/web-health" in dockerfile
