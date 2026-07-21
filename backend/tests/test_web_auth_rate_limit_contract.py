from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_web_auth_rate_limits_separate_polling_from_mutations() -> None:
    nginx = (ROOT / "web/nginx.conf").read_text(encoding="utf-8")

    assert "zone=web_auth_write:10m rate=10r/m" in nginx
    assert "zone=web_auth_poll:10m rate=60r/m" in nginx
    assert "limit_req_status 429;" in nginx
    assert "location = /web/api/auth/session" in nginx
    assert "location ~ ^/web/api/auth/challenges/[0-9a-fA-F-]+$" in nginx
    assert "limit_req zone=web_auth_poll burst=10 nodelay;" in nginx
    assert "limit_req zone=web_auth_write burst=5 nodelay;" in nginx
    assert "zone=web_auth:10m rate=10r/m" not in nginx


def test_caddy_replaces_forwarded_client_address() -> None:
    caddy = (ROOT / "ops/edge/nails-web.enabled.Caddyfile").read_text(
        encoding="utf-8"
    )

    assert "header_up X-Real-IP {remote_host}" in caddy
    assert "header_up X-Forwarded-For {remote_host}" in caddy


def test_login_polling_is_slow_and_consume_retries_are_bounded() -> None:
    script = (
        ROOT / "backend/app/web_static/web001e-copy.js"
    ).read_text(encoding="utf-8")

    assert "CHALLENGE_POLL_INTERVAL_MS = 4500" in script
    assert "MAX_CONSUME_RATE_LIMIT_RETRIES = 4" in script
    assert 'stage === "consume" && [429, 503].includes(error.status)' in script
    assert "Сервер занят. Повторяем открытие кабинета" in script
    assert "Не удалось завершить вход из-за временной нагрузки" in script
    assert "window.setTimeout(pollChallenge, 1800)" not in script
