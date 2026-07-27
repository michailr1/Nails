#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO="/opt/nails/repo"
ENV_FILE="/opt/nails/.env"
FORWARD_INSTALLER="ops/client_forward/deploy_runtime.sh"
RUNTIME_BACKUP_ROOT="/root/.hermes/profiles/nails/backups"

fail() {
  printf 'CLIENT_RUNTIME_PRECONDITION_FAILED=%s\n' "$1" >&2
  exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "root_required"
[[ "$(hostname -f)" == "de.funti.cc" ]] || fail "unexpected_hostname"
[[ -f "$ENV_FILE" ]] || fail "env_missing"
[[ -d "$REPO/.git" ]] || fail "repo_missing"
[[ "$(git -C "$REPO" branch --show-current)" == "main" ]] || fail "production_not_main"
[[ -z "$(git -C "$REPO" status --porcelain)" ]] || fail "production_tree_dirty"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

client_api_enabled="${CLIENT_API_ENABLED:-false}"
client_bot_enabled="${CLIENT_BOT_ENABLED:-false}"
client_internal_key="${CLIENT_INTERNAL_API_KEY:-}"
client_bot_token="${CLIENT_TELEGRAM_BOT_TOKEN:-}"
master_bot_token="${TELEGRAM_BOT_TOKEN:-${TELEGRAM_TOKEN:-}}"

[[ "$client_api_enabled" == "true" ]] || fail "client_api_disabled"
[[ "$client_bot_enabled" == "true" ]] || fail "client_bot_disabled"
[[ ${#client_internal_key} -ge 32 ]] || fail "client_internal_key_missing_or_short"
[[ -n "$client_bot_token" ]] || fail "client_bot_token_missing"
[[ "$client_bot_token" != "$master_bot_token" ]] || fail "client_and_master_bot_tokens_must_differ"

CURRENT_SHA="$(git -C "$REPO" rev-parse HEAD)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUNTIME_BACKUP="${RUNTIME_BACKUP_ROOT}/client-runtime-activation-${STAMP}"
install -d -m 700 "$RUNTIME_BACKUP"

export NAILS_DEPLOY_WORKTREE="$REPO"
bash "$REPO/$FORWARD_INSTALLER" snapshot "$RUNTIME_BACKUP" origin/main

rollback() {
  local code=$?
  trap - ERR
  set +e
  docker compose --project-directory "$REPO" --file "$REPO/compose.yaml" \
    --env-file "$ENV_FILE" stop nails-client-bot >/dev/null 2>&1 || true
  NAILS_DEPLOY_WORKTREE="$REPO" \
    bash "$REPO/$FORWARD_INSTALLER" restore "$RUNTIME_BACKUP" origin/main || true
  printf 'CLIENT_RUNTIME_ACTIVATION_OK=false sha=%s\n' "$CURRENT_SHA" >&2
  exit "$code"
}
trap rollback ERR

python - <<'PY'
import os
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8210/ready", timeout=5) as response:
    if response.status != 200:
        raise SystemExit("API readiness failed")

assert os.environ["CLIENT_API_ENABLED"] == "true"
assert os.environ["CLIENT_BOT_ENABLED"] == "true"
assert len(os.environ["CLIENT_INTERNAL_API_KEY"]) >= 32
assert os.environ["CLIENT_TELEGRAM_BOT_TOKEN"]
PY

NAILS_DEPLOY_WORKTREE="$REPO" \
  bash "$REPO/$FORWARD_INSTALLER" install "$RUNTIME_BACKUP" origin/main

docker compose --project-directory "$REPO" --file "$REPO/compose.yaml" \
  --env-file "$ENV_FILE" build nails-client-bot >/dev/null
docker compose --project-directory "$REPO" --file "$REPO/compose.yaml" \
  --env-file "$ENV_FILE" up -d --no-deps --force-recreate nails-client-bot >/dev/null

state=""
for _ in $(seq 1 30); do
  state="$(docker inspect -f '{{.State.Status}}' nails-nails-client-bot-1 2>/dev/null || true)"
  [[ "$state" == "running" ]] && break
  sleep 1
done
[[ "$state" == "running" ]] || fail "client_bot_not_running"
systemctl is-active --quiet nails-client-forward.service || fail "client_forward_not_running"

BOT_SHA="$(
  docker compose --project-directory "$REPO" --file "$REPO/compose.yaml" \
    --env-file "$ENV_FILE" exec -T nails-client-bot \
    python -c 'import os; print(os.environ.get("NAILS_GIT_SHA", "unknown"))' \
    < /dev/null
)"
[[ "$BOT_SHA" == "$CURRENT_SHA" ]] || fail "client_bot_sha_mismatch"

trap - ERR
printf 'CLIENT_RUNTIME_ACTIVATION_OK=true sha=%s bot_sha=%s forward_active=true\n' \
  "$CURRENT_SHA" "$BOT_SHA"
