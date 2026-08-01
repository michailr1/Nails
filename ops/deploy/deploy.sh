#!/usr/bin/env bash
# Nails — единственный постоянный deploy-скрипт (см. docs/decisions/ADR-003).
#
# Использование:
#   merged main: deploy.sh <exact-sha>
#   open PR:     NAILS_RELEASE_REF=origin/pr/<number> deploy.sh <pr-head-sha>
#   rollback:    NAILS_RELEASE_REF=rollback deploy.sh <previous-sha>
#
# PR candidate проверяется до merge и не меняет production checkout.

set -Eeuo pipefail
umask 077

die() {
  printf 'PRECONDITION_FAILED: %s\n' "$*" >&2
  exit 1
}

[[ -f "${BASH_SOURCE[0]}" ]] || die "deploy.sh must be executed from a regular file, not stdin or a pipe"

RELEASE_SHA="${1:?usage: deploy.sh <exact-commit-sha>}"
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "release must be an exact 40-character commit SHA"

SOURCE_REF="${NAILS_RELEASE_REF:-origin/main}"
[[ "$SOURCE_REF" == "origin/main" || "$SOURCE_REF" == "rollback" || "$SOURCE_REF" =~ ^origin/pr/[0-9]+$ ]] || \
  die "NAILS_RELEASE_REF must be origin/main, rollback or origin/pr/NUMBER"

REPO="/opt/nails/repo"
BACKEND_ENV="/opt/nails/.env"
API_BASE="http://127.0.0.1:8210"
WEB_BASE="http://127.0.0.1:8220"
API_IMAGE="nails-nails-api:latest"
WEB_IMAGE="nails-nails-web:latest"
CLIENT_BOT_IMAGE="nails-nails-client-bot:latest"
LEGACY_CLIENT_BOT_SERVICE="nails-client-bot.service"
LEGACY_CLIENT_BOT_UNIT="/etc/systemd/system/nails-client-bot.service"
LEGACY_CLIENT_BOT_STATUS="/run/nails/client-bot-status.json"
PROFILE="/root/.hermes/profiles/nails"
HERMES_ENV="${PROFILE}/.env"
HERMES_BIN="/usr/local/lib/hermes-agent/venv/bin/hermes"
GATEWAY="hermes-gateway-nails.service"
USER_RUNTIME_DIR="/run/user/0"
BACKUP_ROOT="/opt/nails/backups"
BACKUP_RUNTIME="/opt/nails/backup"
BACKUP_SERVICE="/etc/systemd/system/nails-backup.service"
BACKUP_TIMER="/etc/systemd/system/nails-backup.timer"

PLUGINS=(nails_onboarding nails_scheduling)
SKILLS=(nails-onboarding nails-scheduling)

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORKTREE="/opt/nails/release-${STAMP}"
RUNTIME_BACKUP="${PROFILE}/backups/deploy-${STAMP}"
DB_BACKUP="${BACKUP_ROOT}/nails-before-deploy-${STAMP}.sql.gz"
ROLLBACK_API_IMAGE="nails-nails-api:rollback-${STAMP}"
ROLLBACK_WEB_IMAGE="nails-nails-web:rollback-${STAMP}"
ROLLBACK_CLIENT_BOT_IMAGE="nails-nails-client-bot:rollback-${STAMP}"

log() { printf '== deploy %s: %s ==\n' "$STAMP" "$*"; }
user_systemctl() { XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" systemctl --user "$@"; }
compose() {
  docker compose \
    --project-directory "$WORKTREE" \
    --file "$WORKTREE/compose.yaml" \
    --env-file "$BACKEND_ENV" \
    "$@"
}

API_IMAGE_RETAGGED="false"
WEB_IMAGE_RETAGGED="false"
CLIENT_BOT_IMAGE_RETAGGED="false"
WEB_IMAGE_EXISTED="false"
CLIENT_BOT_IMAGE_EXISTED="false"
WEB_CONTAINER_EXISTED="false"
CLIENT_BOT_CONTAINER_EXISTED="false"
CLIENT_BOT_CONTAINER_WAS_RUNNING="false"
CLIENT_RUNTIME_ENABLED="false"
CLIENT_BOT_SINGLETON="false"
RUNTIME_MUTATED="false"
RUNNING_CLIENT_BOT_SHA="disabled"

validate_client_runtime_config() {
  (
    set -Eeuo pipefail
    set -a
    # shellcheck disable=SC1090
    source "$BACKEND_ENV"
    set +a

    local api_enabled="${CLIENT_API_ENABLED:-false}"
    local bot_enabled="${CLIENT_BOT_ENABLED:-false}"
    if [[ "$api_enabled" == "false" && "$bot_enabled" == "false" ]]; then
      printf 'false\n'
      exit 0
    fi
    [[ "$api_enabled" == "true" && "$bot_enabled" == "true" ]] || {
      printf 'CLIENT_API_ENABLED and CLIENT_BOT_ENABLED must be enabled together\n' >&2
      exit 1
    }
    [[ ${#CLIENT_INTERNAL_API_KEY} -ge 32 ]] || {
      printf 'CLIENT_INTERNAL_API_KEY must contain at least 32 characters\n' >&2
      exit 1
    }
    [[ -n "${CLIENT_TELEGRAM_BOT_TOKEN:-}" ]] || {
      printf 'CLIENT_TELEGRAM_BOT_TOKEN is required when client runtime is enabled\n' >&2
      exit 1
    }
    [[ -f "$HERMES_ENV" ]] || {
      printf 'Hermes env is required for trusted master bot boundary\n' >&2
      exit 1
    }
    local client_token="$CLIENT_TELEGRAM_BOT_TOKEN"

    set -a
    # shellcheck disable=SC1090
    source "$HERMES_ENV"
    set +a
    local master_token="${TELEGRAM_BOT_TOKEN:-${TELEGRAM_TOKEN:-}}"
    [[ -n "$master_token" ]] || {
      printf 'trusted master Telegram bot token is missing\n' >&2
      exit 1
    }
    [[ "$client_token" != "$master_token" ]] || {
      printf 'client and trusted master Telegram bot tokens must differ\n' >&2
      exit 1
    }
    printf 'true\n'
  )
}

remove_legacy_client_bot_runtime() {
  systemctl disable --now "$LEGACY_CLIENT_BOT_SERVICE" >/dev/null 2>&1 || true
  rm -f "$LEGACY_CLIENT_BOT_UNIT" "$LEGACY_CLIENT_BOT_STATUS"
  systemctl daemon-reload
  systemctl is-active --quiet "$LEGACY_CLIENT_BOT_SERVICE" && \
    die "legacy host client bot is still active"
  systemctl is-enabled --quiet "$LEGACY_CLIENT_BOT_SERVICE" && \
    die "legacy host client bot is still enabled"
}

verify_client_bot_singleton() {
  systemctl is-active --quiet "$LEGACY_CLIENT_BOT_SERVICE" && \
    die "legacy host client bot is active"
  systemctl is-enabled --quiet "$LEGACY_CLIENT_BOT_SERVICE" && \
    die "legacy host client bot is enabled"
  [[ ! -e "$LEGACY_CLIENT_BOT_UNIT" ]] || die "legacy host client bot unit still exists"

  local container_count
  container_count="$(docker ps -q --filter 'name=^/nails-nails-client-bot-1$' | wc -l)"
  [[ "$container_count" -eq 1 ]] || die "expected exactly one client bot container"

  compose exec -T nails-client-bot python - <<'PY'
from pathlib import Path

commands = []
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():
        continue
    try:
        commands.append((entry / 'cmdline').read_bytes().replace(b'\0', b' ').decode())
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass

current = [command for command in commands if 'app.client_bot_v1' in command]
legacy = [command for command in commands if 'app.client_bot_runtime' in command]
assert len(current) == 1, current
assert not legacy, legacy
print('CLIENT_BOT_PROCESS_SINGLETON_OK=true')
PY
  CLIENT_BOT_SINGLETON="true"
}

restore_backup_runtime() {
  systemctl stop nails-backup.timer >/dev/null 2>&1 || true
  if [[ -d "${RUNTIME_BACKUP}/backup-runtime.before" ]]; then
    rm -rf "$BACKUP_RUNTIME"
    cp -a "${RUNTIME_BACKUP}/backup-runtime.before" "$BACKUP_RUNTIME"
  else
    rm -rf "$BACKUP_RUNTIME"
  fi
  if [[ -f "${RUNTIME_BACKUP}/nails-backup.service.before" ]]; then
    cp -a "${RUNTIME_BACKUP}/nails-backup.service.before" "$BACKUP_SERVICE"
  else
    rm -f "$BACKUP_SERVICE"
  fi
  if [[ -f "${RUNTIME_BACKUP}/nails-backup.timer.before" ]]; then
    cp -a "${RUNTIME_BACKUP}/nails-backup.timer.before" "$BACKUP_TIMER"
  else
    rm -f "$BACKUP_TIMER"
  fi
  systemctl daemon-reload
  if [[ "$(cat "${RUNTIME_BACKUP}/backup-timer-enabled.before" 2>/dev/null)" == enabled ]]; then
    systemctl enable nails-backup.timer >/dev/null 2>&1
  else
    systemctl disable nails-backup.timer >/dev/null 2>&1 || true
  fi
  if [[ "$(cat "${RUNTIME_BACKUP}/backup-timer-active.before" 2>/dev/null)" == active ]]; then
    systemctl start nails-backup.timer >/dev/null 2>&1
  fi
}

restore_images() {
  if [[ "$API_IMAGE_RETAGGED" == "true" ]]; then
    docker image tag "$ROLLBACK_API_IMAGE" "$API_IMAGE" >/dev/null 2>&1
    printf 'DEPLOY_API_IMAGE_TAG_RESTORED=true\n'
  fi
  if [[ "$WEB_IMAGE_RETAGGED" == "true" ]]; then
    docker image tag "$ROLLBACK_WEB_IMAGE" "$WEB_IMAGE" >/dev/null 2>&1
    printf 'DEPLOY_WEB_IMAGE_TAG_RESTORED=true\n'
  elif [[ "$WEB_IMAGE_EXISTED" == "false" ]]; then
    docker image rm "$WEB_IMAGE" >/dev/null 2>&1 || true
  fi
  if [[ "$CLIENT_BOT_IMAGE_RETAGGED" == "true" ]]; then
    docker image tag "$ROLLBACK_CLIENT_BOT_IMAGE" "$CLIENT_BOT_IMAGE" >/dev/null 2>&1
    printf 'DEPLOY_CLIENT_BOT_IMAGE_TAG_RESTORED=true\n'
  elif [[ "$CLIENT_BOT_IMAGE_EXISTED" == "false" ]]; then
    docker image rm "$CLIENT_BOT_IMAGE" >/dev/null 2>&1 || true
  fi
}

restore_containers() {
  compose up -d --no-deps --force-recreate --no-build nails-api >/dev/null 2>&1
  if [[ "$WEB_CONTAINER_EXISTED" == "true" ]]; then
    compose up -d --no-deps --force-recreate --no-build nails-web >/dev/null 2>&1
  else
    compose rm -sf nails-web >/dev/null 2>&1 || true
  fi
  if [[ "$CLIENT_BOT_CONTAINER_EXISTED" == "true" ]]; then
    compose up -d --no-deps --force-recreate --no-build nails-client-bot >/dev/null 2>&1
    if [[ "$CLIENT_BOT_CONTAINER_WAS_RUNNING" != "true" ]]; then
      compose stop nails-client-bot >/dev/null 2>&1 || true
    fi
  else
    compose rm -sf nails-client-bot >/dev/null 2>&1 || true
  fi
}

on_error() {
  local exit_code=$?
  trap - ERR
  set +e

  log "FAILED (exit ${exit_code})"
  restore_images

  if [[ "$RUNTIME_MUTATED" == "true" ]]; then
    log "rollback: restoring previous images, containers, plugins, skills, timers, client runtime and gateway"
    restore_containers
    [[ -d "${RUNTIME_BACKUP}/plugins.before" ]] && {
      rm -rf "${PROFILE}/plugins"
      cp -a "${RUNTIME_BACKUP}/plugins.before" "${PROFILE}/plugins"
    }
    [[ -d "${RUNTIME_BACKUP}/skills.before" ]] && {
      rm -rf "${PROFILE}/skills"
      cp -a "${RUNTIME_BACKUP}/skills.before" "${PROFILE}/skills"
    }
    restore_backup_runtime
    NAILS_DEPLOY_WORKTREE="$WORKTREE" \
      bash "$WORKTREE/ops/digest/deploy_runtime.sh" restore "$RUNTIME_BACKUP" "$SOURCE_REF"
    NAILS_DEPLOY_WORKTREE="$WORKTREE" \
      bash "$WORKTREE/ops/client_forward/deploy_runtime.sh" restore "$RUNTIME_BACKUP" "$SOURCE_REF"
    remove_legacy_client_bot_runtime
    user_systemctl start "$GATEWAY" >/dev/null 2>&1
    printf 'DEPLOY_ROLLED_BACK=true prev_sha=%s\n' "$PREV_SHA"
  else
    printf 'DEPLOY_ROLLED_BACK=false\n'
  fi

  [[ -d "$RUNTIME_BACKUP" ]] && mv "$RUNTIME_BACKUP" "${PROFILE}/backups/deploy-failed-${STAMP}"
  docker image rm "$ROLLBACK_API_IMAGE" >/dev/null 2>&1 || true
  docker image rm "$ROLLBACK_WEB_IMAGE" >/dev/null 2>&1 || true
  docker image rm "$ROLLBACK_CLIENT_BOT_IMAGE" >/dev/null 2>&1 || true
  git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1
  exit "$exit_code"
}
trap on_error ERR

wait_api_ready() {
  for _ in $(seq 1 60); do
    if curl -fsS "${API_BASE}/ready" 2>/dev/null | grep -q '"ready"'; then
      return 0
    fi
    sleep 1
  done
  echo "ERROR: API did not become ready" >&2
  return 1
}

wait_web_ready() {
  for _ in $(seq 1 60); do
    if curl -fsS "${WEB_BASE}/web-health" 2>/dev/null | grep -q '"ok"'; then
      return 0
    fi
    sleep 1
  done
  echo "ERROR: WEB did not become ready" >&2
  return 1
}

wait_client_bot_running() {
  for _ in $(seq 1 30); do
    if [[ "$(docker inspect -f '{{.State.Status}}' nails-nails-client-bot-1 2>/dev/null || true)" == running ]]; then
      return 0
    fi
    sleep 1
  done
  echo "ERROR: client bot did not become running" >&2
  return 1
}

log "0. Предусловия"
[[ "$(id -u)" -eq 0 ]] || die "root is required"
[[ "$(hostname -f)" == "de.funti.cc" ]] || die "unexpected hostname"
[[ -f "$BACKEND_ENV" ]] || die "backend env file is missing"
[[ "$(git -C "$REPO" branch --show-current)" == "main" ]] || die "production checkout is not on main"
[[ -z "$(git -C "$REPO" status --porcelain)" ]] || die "production checkout is not clean"

if [[ "$SOURCE_REF" == "origin/main" ]]; then
  git -C "$REPO" fetch origin main
fi

git -C "$REPO" worktree prune --expire now
git -C "$REPO" cat-file -e "${RELEASE_SHA}^{commit}"
PREV_SHA="$(git -C "$REPO" rev-parse HEAD)"

if [[ "$SOURCE_REF" == "rollback" ]]; then
  git -C "$REPO" merge-base --is-ancestor "$RELEASE_SHA" "$PREV_SHA" || \
    die "rollback SHA is not an ancestor of the current production checkout"
else
  [[ "$(git -C "$REPO" rev-parse "$SOURCE_REF")" == "$RELEASE_SHA" ]] || \
    die "source ref does not equal the approved release SHA"
  git -C "$REPO" merge-base --is-ancestor "$PREV_SHA" "$RELEASE_SHA" || \
    die "release SHA is not based on the current production checkout"
fi
printf 'prev_sha=%s release_sha=%s source_ref=%s\n' "$PREV_SHA" "$RELEASE_SHA" "$SOURCE_REF"

log "1. Точное дерево релиза"
git -C "$REPO" worktree add --detach "$WORKTREE" "$RELEASE_SHA" >/dev/null
[[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$RELEASE_SHA" ]]
CLIENT_RUNTIME_ENABLED="$(validate_client_runtime_config)" || die "invalid client runtime configuration"
printf 'client_runtime_enabled=%s\n' "$CLIENT_RUNTIME_ENABLED"

log "2. Бэкапы базы и runtime"
install -d -m 700 "$BACKUP_ROOT" "$RUNTIME_BACKUP"
compose exec -T nails-db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  < /dev/null | gzip -9 >"$DB_BACKUP"
chmod 600 "$DB_BACKUP"
[[ -s "$DB_BACKUP" ]]
gzip -t "$DB_BACKUP"
cp -a "${PROFILE}/plugins" "${RUNTIME_BACKUP}/plugins.before"
cp -a "${PROFILE}/skills" "${RUNTIME_BACKUP}/skills.before"
[[ -d "$BACKUP_RUNTIME" ]] && cp -a "$BACKUP_RUNTIME" "${RUNTIME_BACKUP}/backup-runtime.before"
[[ -f "$BACKUP_SERVICE" ]] && cp -a "$BACKUP_SERVICE" "${RUNTIME_BACKUP}/nails-backup.service.before"
[[ -f "$BACKUP_TIMER" ]] && cp -a "$BACKUP_TIMER" "${RUNTIME_BACKUP}/nails-backup.timer.before"
systemctl is-enabled nails-backup.timer >"${RUNTIME_BACKUP}/backup-timer-enabled.before" 2>/dev/null || true
systemctl is-active nails-backup.timer >"${RUNTIME_BACKUP}/backup-timer-active.before" 2>/dev/null || true
NAILS_DEPLOY_WORKTREE="$WORKTREE" \
  bash "$WORKTREE/ops/digest/deploy_runtime.sh" snapshot "$RUNTIME_BACKUP" "$SOURCE_REF"
NAILS_DEPLOY_WORKTREE="$WORKTREE" \
  bash "$WORKTREE/ops/client_forward/deploy_runtime.sh" snapshot "$RUNTIME_BACKUP" "$SOURCE_REF"

if docker image inspect "$WEB_IMAGE" >/dev/null 2>&1; then
  WEB_IMAGE_EXISTED="true"
fi
if docker image inspect "$CLIENT_BOT_IMAGE" >/dev/null 2>&1; then
  CLIENT_BOT_IMAGE_EXISTED="true"
fi
if docker ps -aq --filter 'name=^/nails-nails-web-1$' | grep -q .; then
  WEB_CONTAINER_EXISTED="true"
fi
if docker ps -aq --filter 'name=^/nails-nails-client-bot-1$' | grep -q .; then
  CLIENT_BOT_CONTAINER_EXISTED="true"
fi
if docker ps -q --filter 'name=^/nails-nails-client-bot-1$' | grep -q .; then
  CLIENT_BOT_CONTAINER_WAS_RUNNING="true"
fi
printf 'web_image_existed=%s web_container_existed=%s client_bot_image_existed=%s client_bot_container_existed=%s client_bot_was_running=%s\n' \
  "$WEB_IMAGE_EXISTED" "$WEB_CONTAINER_EXISTED" "$CLIENT_BOT_IMAGE_EXISTED" \
  "$CLIENT_BOT_CONTAINER_EXISTED" "$CLIENT_BOT_CONTAINER_WAS_RUNNING"

log "3. Сборка образов из точного дерева"
docker image tag "$API_IMAGE" "$ROLLBACK_API_IMAGE"
API_IMAGE_RETAGGED="true"
if [[ "$WEB_IMAGE_EXISTED" == "true" ]]; then
  docker image tag "$WEB_IMAGE" "$ROLLBACK_WEB_IMAGE"
  WEB_IMAGE_RETAGGED="true"
fi
if [[ "$CLIENT_BOT_IMAGE_EXISTED" == "true" ]]; then
  docker image tag "$CLIENT_BOT_IMAGE" "$ROLLBACK_CLIENT_BOT_IMAGE"
  CLIENT_BOT_IMAGE_RETAGGED="true"
fi
compose build --build-arg GIT_SHA="$RELEASE_SHA" nails-api nails-web nails-client-bot >/dev/null

log "4. Проверка собранных образов ДО остановки runtime"
docker run --rm -i --network none --read-only --tmpfs /tmp:size=16m \
  -e EXPECTED_SHA="$RELEASE_SHA" \
  -e APP_TIMEZONE=UTC \
  -e DATABASE_URL=postgresql+psycopg://smoke:smoke@127.0.0.1:5432/smoke \
  -e INTERNAL_API_KEY=deploy-smoke-key-0000000000000000 \
  "$API_IMAGE" python - <<'PY'
import os

expected = os.environ["EXPECTED_SHA"]
actual = os.environ.get("NAILS_GIT_SHA", "unknown")
assert actual == expected, f"image built from wrong tree: {actual!r} != {expected!r}"

from app.api.client_contour import router as client_contour_router
from app.api.client_forward import router as client_forward_router
from app.api.onboarding import router as onboarding_router
from app.api.scheduling import router as scheduling_router
from app.api.scheduling_digest import router as scheduling_digest_router
from app.main import app

onboarding_paths = {getattr(route, "path", "") for route in onboarding_router.routes}
scheduling_paths = {getattr(route, "path", "") for route in scheduling_router.routes}
digest_paths = {getattr(route, "path", "") for route in scheduling_digest_router.routes}
client_paths = {getattr(route, "path", "") for route in client_contour_router.routes}
forward_paths = {getattr(route, "path", "") for route in client_forward_router.routes}
app_paths = {getattr(route, "path", "") for route in app.routes}

assert any(path.startswith("/api/v1/onboarding") for path in onboarding_paths), sorted(onboarding_paths)
assert any(path.startswith("/api/v1/scheduling") for path in scheduling_paths), sorted(scheduling_paths)
assert "/api/v1/scheduling/finalization-digest/claim" in digest_paths, sorted(digest_paths)
assert "/api/v1/scheduling/finalization-digest/ack" in digest_paths, sorted(digest_paths)
assert "/api/v1/client/start" in client_paths, sorted(client_paths)
assert "/api/v1/client/context" in client_paths, sorted(client_paths)
assert "/api/v1/client/contact-forward" in forward_paths, sorted(forward_paths)
assert "/api/v1/client/contact-forward/internal/claim" in forward_paths, sorted(forward_paths)
assert "/health" in app_paths and "/ready" in app_paths, sorted(app_paths)
print("BUILT_API_IMAGE_OK=true")
PY

bash -n "$WORKTREE/ops/digest/deploy_runtime.sh"
"/usr/local/lib/hermes-agent/venv/bin/python" -m py_compile "$WORKTREE/ops/digest/send.py"
systemd-analyze verify \
  "$WORKTREE/ops/digest/nails-finalization-digest.service" \
  "$WORKTREE/ops/digest/nails-finalization-digest.timer" >/dev/null
bash -n "$WORKTREE/ops/client_forward/deploy_runtime.sh"
"/usr/local/lib/hermes-agent/venv/bin/python" -m py_compile "$WORKTREE/ops/client_forward/send.py"
systemd-analyze verify "$WORKTREE/ops/client_forward/nails-client-forward.service" >/dev/null

CLIENT_BOT_BUILT_SHA="$(
  docker run --rm --network none "$CLIENT_BOT_IMAGE" \
    python -c 'import os; from app.client_bot_v1 import run; print(os.environ.get("NAILS_GIT_SHA", "unknown"))'
)"
[[ "$CLIENT_BOT_BUILT_SHA" == "$RELEASE_SHA" ]] || die "client bot image built from wrong tree"
printf 'BUILT_CLIENT_BOT_IMAGE_OK=true sha=%s\n' "$CLIENT_BOT_BUILT_SHA"

docker run --rm --network none --read-only --tmpfs /var/cache/nginx:size=16m \
  --tmpfs /var/run:size=1m --tmpfs /tmp:size=8m \
  "$WEB_IMAGE" nginx -t >/dev/null
WEB_BUILT_SHA="$(docker run --rm --network none "$WEB_IMAGE" sh -c 'printf %s "$NAILS_GIT_SHA"')"
[[ "$WEB_BUILT_SHA" == "$RELEASE_SHA" ]] || die "WEB image built from wrong tree"
printf 'BUILT_WEB_IMAGE_OK=true sha=%s\n' "$WEB_BUILT_SHA"

log "5. Остановка digest, client runtime, gateway и перезапуск nails-api + nails-web"
RUNTIME_MUTATED="true"
remove_legacy_client_bot_runtime
NAILS_DEPLOY_WORKTREE="$WORKTREE" \
  bash "$WORKTREE/ops/digest/deploy_runtime.sh" stop "$RUNTIME_BACKUP" "$SOURCE_REF"
NAILS_DEPLOY_WORKTREE="$WORKTREE" \
  bash "$WORKTREE/ops/client_forward/deploy_runtime.sh" stop "$RUNTIME_BACKUP" "$SOURCE_REF"
compose stop nails-client-bot >/dev/null 2>&1 || true
user_systemctl stop "$GATEWAY"
compose up -d --no-deps --force-recreate --no-build nails-api nails-web >/dev/null
wait_api_ready
wait_web_ready
RUNNING_SHA="$(
  compose exec -T nails-api \
    python -c 'import os; print(os.environ.get("NAILS_GIT_SHA", "unknown"))' \
    < /dev/null
)"
[[ "$RUNNING_SHA" == "$RELEASE_SHA" ]] || {
  echo "ERROR: running API container SHA mismatch: ${RUNNING_SHA}" >&2
  exit 1
}
RUNNING_WEB_SHA="$(
  compose exec -T nails-web sh -c 'printf %s "$NAILS_GIT_SHA"' < /dev/null
)"
[[ "$RUNNING_WEB_SHA" == "$RELEASE_SHA" ]] || {
  echo "ERROR: running WEB container SHA mismatch: ${RUNNING_WEB_SHA}" >&2
  exit 1
}

log "6. Установка plugins, skills, backup, digest и client runtime из релизного дерева"
for name in "${PLUGINS[@]}"; do
  src="${WORKTREE}/hermes/plugins/${name}"
  dst="${PROFILE}/plugins/${name}"
  rm -rf "$dst"
  install -d -o root -g root -m 700 "$dst"
  find "$src" -maxdepth 1 -type f ! -name 'README.md' \
    -exec install -o root -g root -m 600 {} "$dst"/ \;
done
for name in "${SKILLS[@]}"; do
  install -o root -g root -m 600 \
    "${WORKTREE}/hermes/skills/${name}/SKILL.md" \
    "${PROFILE}/skills/${name}/SKILL.md"
done
HERMES_HOME="$PROFILE" "$HERMES_BIN" --profile nails config check >/dev/null

rm -rf "$BACKUP_RUNTIME"
install -d -o root -g root -m 700 "$BACKUP_RUNTIME"
install -o root -g root -m 700 "${WORKTREE}/ops/backup/backup.sh" "$BACKUP_RUNTIME/backup.sh"
install -o root -g root -m 700 "${WORKTREE}/ops/backup/retention.py" "$BACKUP_RUNTIME/retention.py"
install -o root -g root -m 644 "${WORKTREE}/ops/backup/nails-backup.service" "$BACKUP_SERVICE"
install -o root -g root -m 644 "${WORKTREE}/ops/backup/nails-backup.timer" "$BACKUP_TIMER"
systemctl daemon-reload
systemctl enable --now nails-backup.timer >/dev/null
systemctl is-enabled --quiet nails-backup.timer
systemctl is-active --quiet nails-backup.timer
NAILS_DEPLOY_WORKTREE="$WORKTREE" \
  bash "$WORKTREE/ops/digest/deploy_runtime.sh" install "$RUNTIME_BACKUP" "$SOURCE_REF"
NAILS_DEPLOY_WORKTREE="$WORKTREE" \
NAILS_CLIENT_FORWARD_DESIRED_ACTIVE="$CLIENT_RUNTIME_ENABLED" \
  bash "$WORKTREE/ops/client_forward/deploy_runtime.sh" install "$RUNTIME_BACKUP" "$SOURCE_REF"

if [[ "$CLIENT_RUNTIME_ENABLED" == "true" ]]; then
  compose up -d --no-deps --force-recreate --no-build nails-client-bot >/dev/null
  wait_client_bot_running
  systemctl is-enabled --quiet nails-client-forward.service
  systemctl is-active --quiet nails-client-forward.service
  RUNNING_CLIENT_BOT_SHA="$(
    compose exec -T nails-client-bot \
      python -c 'import os; print(os.environ.get("NAILS_GIT_SHA", "unknown"))' \
      < /dev/null
  )"
  [[ "$RUNNING_CLIENT_BOT_SHA" == "$RELEASE_SHA" ]] || die "running client bot SHA mismatch"
  verify_client_bot_singleton
else
  compose rm -sf nails-client-bot >/dev/null 2>&1 || true
  systemctl is-active --quiet nails-client-forward.service && die "client forward is active while client runtime is disabled"
  systemctl is-active --quiet "$LEGACY_CLIENT_BOT_SERVICE" && die "legacy client bot active while disabled"
  RUNNING_CLIENT_BOT_SHA="disabled"
  CLIENT_BOT_SINGLETON="true"
fi

log "7. Старт gateway"
user_systemctl start "$GATEWAY"
for _ in $(seq 1 60); do
  user_systemctl is-active --quiet "$GATEWAY" && break
  sleep 1
done
user_systemctl is-active --quiet "$GATEWAY"

log "8. Фиксация результата"
git -C "$REPO" worktree remove --force "$WORKTREE"

if [[ "$SOURCE_REF" =~ ^origin/pr/[0-9]+$ ]]; then
  [[ "$(git -C "$REPO" rev-parse HEAD)" == "$PREV_SHA" ]] || \
    die "candidate deployment changed production checkout"
  [[ -z "$(git -C "$REPO" status --porcelain)" ]] || \
    die "candidate deployment dirtied production checkout"
else
  git -C "$REPO" checkout main >/dev/null 2>&1
  if git -C "$REPO" merge-base --is-ancestor "$PREV_SHA" "$RELEASE_SHA"; then
    git -C "$REPO" merge --ff-only "$RELEASE_SHA" >/dev/null
  else
    git -C "$REPO" reset --hard "$RELEASE_SHA" >/dev/null
  fi
  [[ "$(git -C "$REPO" rev-parse HEAD)" == "$RELEASE_SHA" ]]
  [[ -z "$(git -C "$REPO" status --porcelain)" ]]
fi

mv "$RUNTIME_BACKUP" "${PROFILE}/backups/deploy-success-${STAMP}"
docker image rm "$ROLLBACK_API_IMAGE" >/dev/null 2>&1 || true
docker image rm "$ROLLBACK_WEB_IMAGE" >/dev/null 2>&1 || true
docker image rm "$ROLLBACK_CLIENT_BOT_IMAGE" >/dev/null 2>&1 || true
trap - ERR

if [[ "$SOURCE_REF" =~ ^origin/pr/[0-9]+$ ]]; then
  printf 'CANDIDATE_DEPLOY_OK=true candidate_sha=%s baseline_sha=%s running_sha=%s running_web_sha=%s client_runtime_enabled=%s running_client_bot_sha=%s client_bot_singleton=%s db_backup=%s\n' \
    "$RELEASE_SHA" "$PREV_SHA" "$RUNNING_SHA" "$RUNNING_WEB_SHA" "$CLIENT_RUNTIME_ENABLED" \
    "$RUNNING_CLIENT_BOT_SHA" "$CLIENT_BOT_SINGLETON" "$DB_BACKUP"
else
  printf 'DEPLOY_OK=true sha=%s prev_sha=%s running_web_sha=%s client_runtime_enabled=%s running_client_bot_sha=%s client_bot_singleton=%s db_backup=%s\n' \
    "$RELEASE_SHA" "$PREV_SHA" "$RUNNING_WEB_SHA" "$CLIENT_RUNTIME_ENABLED" \
    "$RUNNING_CLIENT_BOT_SHA" "$CLIENT_BOT_SINGLETON" "$DB_BACKUP"
fi
