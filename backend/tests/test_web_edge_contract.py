from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_keeps_api_and_web_on_loopback():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    api_binding = '${NAILS_API_BIND:-127.0.0.1}:${NAILS_API_PORT:-8210}:8000'
    web_binding = '${NAILS_WEB_BIND:-127.0.0.1}:${NAILS_WEB_PORT:-8220}:8080'
    assert api_binding in compose
    assert web_binding in compose
    assert "WEB_AUTH_ENABLED: ${WEB_AUTH_ENABLED:-false}" in compose
    assert "WEB_AUTH_HMAC_KEY: ${WEB_AUTH_HMAC_KEY:-}" in compose
    assert "nails-web:" in compose
    assert "condition: service_healthy" in compose


def test_web_edge_only_proxies_browser_api_namespace():
    config = (ROOT / "web" / "nginx.conf").read_text(encoding="utf-8")

    assert "location ^~ /web/api/auth/" in config
    assert "location ^~ /web/api/" in config
    assert "proxy_pass http://nails-api:8000;" in config
    assert "/api/v1/" not in config
    assert "client_max_body_size 16k;" in config
    assert "limit_req zone=web_auth" in config
    assert "frame-ancestors 'none'" in config


def test_web_edge_image_is_unprivileged_and_health_checked():
    dockerfile = (ROOT / "web" / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM nginxinc/nginx-unprivileged:")
    assert "EXPOSE 8080" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/web-health" in dockerfile
