#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

EXPECTED_SHA="${1:?usage: activate.sh <exact-production-sha>}"
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid SHA" >&2; exit 2; }

REPO="/opt/nails/repo"
BACKEND_ENV="/opt/nails/.env"
HERMES_ENV="/root/.hermes/profiles/nails/.env"
SERVICE_SOURCE="$REPO/ops/client_bot/nails-client-bot.service"
SERVICE_TARGET="/etc/systemd/system/nails-client-bot.service"

[[ "$(id -u)" -eq 0 ]] || { echo "root required" >&2; exit 2; }
[[ "$(hostname -f)" == "de.funti.cc" ]] || { echo "unexpected hostname" >&2; exit 2; }
[[ -f "$BACKEND_ENV" ]] || { echo "backend env missing" >&2; exit 2; }
[[ -f "$HERMES_ENV" ]] || { echo "master bot env missing" >&2; exit 2; }
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$EXPECTED_SHA" ]] || { echo "production SHA mismatch" >&2; exit 2; }
[[ -z "$(git -C "$REPO" status --porcelain)" ]] || { echo "production checkout dirty" >&2; exit 2; }

set -a
# shellcheck disable=SC1090
source "$BACKEND_ENV"
set +a
[[ "${CLIENT_API_ENABLED:-false}" == "true" ]] || { echo "CLIENT_API_ENABLED must be true" >&2; exit 2; }
[[ "${CLIENT_BOT_ENABLED:-false}" == "true" ]] || { echo "CLIENT_BOT_ENABLED must be true" >&2; exit 2; }
[[ ${#CLIENT_INTERNAL_API_KEY} -ge 32 ]] || { echo "CLIENT_INTERNAL_API_KEY too short" >&2; exit 2; }
[[ -n "${CLIENT_TELEGRAM_BOT_TOKEN:-}" ]] || { echo "CLIENT_TELEGRAM_BOT_TOKEN missing" >&2; exit 2; }
[[ "$CLIENT_INTERNAL_API_KEY" != "${INTERNAL_API_KEY:-}" ]] || { echo "client and master internal keys must differ" >&2; exit 2; }
client_token="$CLIENT_TELEGRAM_BOT_TOKEN"

set -a
# shellcheck disable=SC1090
source "$HERMES_ENV"
set +a
master_token="${TELEGRAM_BOT_TOKEN:-${TELEGRAM_TOKEN:-}}"
[[ -n "$master_token" ]] || { echo "master Telegram token missing" >&2; exit 2; }
[[ "$client_token" != "$master_token" ]] || { echo "client and master Telegram tokens must differ" >&2; exit 2; }

systemd-analyze verify "$SERVICE_SOURCE" >/dev/null
install -o root -g root -m 644 "$SERVICE_SOURCE" "$SERVICE_TARGET"
systemctl daemon-reload
systemctl enable --now nails-client-forward.service >/dev/null
systemctl enable --now nails-client-bot.service >/dev/null
systemctl is-active --quiet nails-client-forward.service
systemctl is-active --quiet nails-client-bot.service

for _ in $(seq 1 6); do
  if /usr/local/lib/hermes-agent/venv/bin/python "$REPO/ops/client_bot/health.py"; then
    echo "CLIENT_RUNTIME_ACTIVATED=true sha=$EXPECTED_SHA"
    exit 0
  fi
  sleep 10
done

echo "client bot health did not become ready" >&2
exit 1
