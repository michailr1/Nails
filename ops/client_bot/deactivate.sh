#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

EXPECTED_SHA="${1:?usage: deactivate.sh <exact-production-sha>}"
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid SHA" >&2; exit 2; }

REPO="/opt/nails/repo"
BACKEND_ENV="/opt/nails/.env"
API_BASE="http://127.0.0.1:8210"

compose() {
  docker compose \
    --project-directory "$REPO" \
    --file "$REPO/compose.yaml" \
    --env-file "$BACKEND_ENV" \
    "$@"
}

[[ "$(id -u)" -eq 0 ]] || { echo "root required" >&2; exit 2; }
[[ "$(hostname -f)" == "de.funti.cc" ]] || { echo "unexpected hostname" >&2; exit 2; }
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$EXPECTED_SHA" ]] || { echo "production SHA mismatch" >&2; exit 2; }
[[ -z "$(git -C "$REPO" status --porcelain)" ]] || { echo "production checkout dirty" >&2; exit 2; }
[[ -f "$BACKEND_ENV" ]] || { echo "backend env missing" >&2; exit 2; }

set -a
# shellcheck disable=SC1090
source "$BACKEND_ENV"
set +a
[[ "${CLIENT_API_ENABLED:-false}" == "false" ]] || { echo "set CLIENT_API_ENABLED=false before deactivation" >&2; exit 2; }
[[ "${CLIENT_BOT_ENABLED:-false}" == "false" ]] || { echo "set CLIENT_BOT_ENABLED=false before deactivation" >&2; exit 2; }

systemctl disable --now nails-client-bot.service >/dev/null 2>&1 || true
systemctl disable --now nails-client-forward.service >/dev/null 2>&1 || true
rm -f /run/nails/client-bot-status.json
compose stop nails-client-bot >/dev/null 2>&1 || true
compose rm -sf nails-client-bot >/dev/null 2>&1 || true

compose up -d --no-deps --force-recreate --no-build nails-api >/dev/null
for _ in $(seq 1 30); do
  curl -fsS "$API_BASE/ready" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "$API_BASE/ready" >/dev/null

systemctl is-active --quiet nails-client-bot.service && { echo "client bot still active" >&2; exit 1; }
echo "CLIENT_RUNTIME_DEACTIVATED=true sha=$EXPECTED_SHA"
