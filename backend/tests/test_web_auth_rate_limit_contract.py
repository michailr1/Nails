from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_web_auth_rate_limits_route_consume_outside_write_bucket() -> None:
    nginx = (ROOT / "web/nginx.conf").read_text(encoding="utf-8")

    consume_location = "location = /web/api/auth/challenges/consume"
    auth_fallback = "location ^~ /web/api/auth/"

    assert "zone=web_auth_write:10m rate=30r/m" in nginx
    assert "zone=web_auth_poll:10m rate=60r/m" in nginx
    assert "limit_req_status 429;" in nginx
    assert "location = /web/api/auth/session" in nginx
    assert consume_location in nginx
    assert "location ~ ^/web/api/auth/challenges/[0-9a-fA-F-]+$" in nginx
    assert nginx.index(consume_location) < nginx.index(auth_fallback)

    consume_block = nginx.split(consume_location, 1)[1].split("location ", 1)[0]
    fallback_block = nginx.split(auth_fallback, 1)[1].split("location ", 1)[0]
    assert "limit_req zone=web_auth_poll burst=10 nodelay;" in consume_block
    assert "limit_req zone=web_auth_write burst=10 nodelay;" in fallback_block
    assert "zone=web_auth:10m rate=10r/m" not in nginx


def test_caddy_replaces_forwarded_client_address() -> None:
    caddy = (ROOT / "ops/edge/nails-web.enabled.Caddyfile").read_text(
        encoding="utf-8"
    )

    assert "header_up X-Real-IP {remote_host}" in caddy
    assert "header_up X-Forwarded-For {remote_host}" in caddy


def test_login_polling_is_slow_and_consume_retries_are_bounded() -> None:
    script = (ROOT / "backend/app/web_static/web001e-copy.js").read_text(
        encoding="utf-8"
    )

    assert "CHALLENGE_POLL_INTERVAL_MS = 4500" in script
    assert "MAX_CONSUME_RATE_LIMIT_RETRIES = 3" in script
    assert 'stage === "consume" && [429, 503].includes(error.status)' in script
    assert "consumeRateLimitRetries >= MAX_CONSUME_RATE_LIMIT_RETRIES" in script
    assert "failConsumeLogin()" in script
    assert "Получите новое число и войдите заново" in script
    assert "window.setTimeout(pollChallenge, 1800)" not in script
