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
API_IMAGE="nails-nails-api:latest"
PROFILE="/root/.hermes/profiles/nails"
HERMES_BIN="/usr/local/lib/hermes-agent/venv/bin/hermes"
GATEWAY="hermes-gateway-nails.service"
USER_RUNTIME_DIR="/run/user/0"
BACKUP_ROOT="/opt/nails/backups"
BACKUP_RUNTIME="/opt/nails/backup"
BACKUP_SERVICE="/etc/systemd/system/nails-backup.service"
BACKUP_TIMER="/etc/systemd/system/nails-backup.timer"

PLUGINS=(nails_onboarding nails_scheduling)
SKILLS=(nails-onboarding nails-scheduling nails-feedback)

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORKTREE="/opt/nails/release-${STAMP}"
RUNTIME_BACKUP="${PROFILE}/backups/deploy-${STAMP}"
DB_BACKUP="${BACKUP_ROOT}/nails-before-deploy-${STAMP}.sql.gz"
ROLLBACK_IMAGE="nails-nails-api:rollback-${STAMP}"

log() { printf '== deploy %s: %s ==\n' "$STAMP" "$*"; }
user_systemctl() { XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" systemctl --user "$@"; }
compose() {
  docker compose \
    --project-directory "$WORKTREE" \
    --file "$WORKTREE/compose.yaml" \
    --env-file "$BACKEND_ENV" \
    "$@"
}

IMAGE_RETAGGED="false"
RUNTIME_MUTATED="false"

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

on_error() {
  local exit_code=$?
  trap - ERR
  set +e

  log "FAILED (exit ${exit_code})"

  if [[ "$IMAGE_RETAGGED" == "true" ]]; then
    docker image tag "$ROLLBACK_IMAGE" "$API_IMAGE" >/dev/null 2>&1
    printf 'DEPLOY_IMAGE_TAG_RESTORED=true\n'
  fi

  if [[ "$RUNTIME_MUTATED" == "true" ]]; then
    log "rollback: restoring previous image, plugins, skills, backup timer and gateway"
    compose up -d --no-deps --force-recreate --no-build nails-api >/dev/null 2>&1
    [[ -d "${RUNTIME_BACKUP}/plugins.before" ]] && {
      rm -rf "${PROFILE}/plugins"
      cp -a "${RUNTIME_BACKUP}/plugins.before" "${PROFILE}/plugins"
    }
    [[ -d "${RUNTIME_BACKUP}/skills.before" ]] && {
      rm -rf "${PROFILE}/skills"
      cp -a "${RUNTIME_BACKUP}/skills.before" "${PROFILE}/skills"
    }
    restore_backup_runtime
    user_systemctl start "$GATEWAY" >/dev/null 2>&1
    printf 'DEPLOY_ROLLED_BACK=true prev_sha=%s\n' "$PREV_SHA"
  else
    printf 'DEPLOY_ROLLED_BACK=false\n'
  fi

  [[ -d "$RUNTIME_BACKUP" ]] && mv "$RUNTIME_BACKUP" "${PROFILE}/backups/deploy-failed-${STAMP}"
  docker image rm "$ROLLBACK_IMAGE" >/dev/null 2>&1
  git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1
  exit "$exit_code"
}
trap on_error ERR

wait_ready() {
  for _ in $(seq 1 60); do
    if curl -fsS "${API_BASE}/ready" 2>/dev/null | grep -q '"ready"'; then
      return 0
    fi
    sleep 1
  done
  echo "ERROR: API did not become ready" >&2
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

log "3. Сборка образа из точного дерева"
docker image tag "$API_IMAGE" "$ROLLBACK_IMAGE"
compose build --build-arg GIT_SHA="$RELEASE_SHA" nails-api >/dev/null
IMAGE_RETAGGED="true"

log "4. Проверка собранного образа ДО остановки runtime"
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

from app.api.onboarding import router as onboarding_router
from app.api.scheduling import router as scheduling_router
from app.main import app

onboarding_paths = {getattr(route, "path", "") for route in onboarding_router.routes}
scheduling_paths = {getattr(route, "path", "") for route in scheduling_router.routes}
app_paths = {getattr(route, "path", "") for route in app.routes}

assert any(path.startswith("/api/v1/onboarding") for path in onboarding_paths), sorted(onboarding_paths)
assert any(path.startswith("/api/v1/scheduling") for path in scheduling_paths), sorted(scheduling_paths)
assert "/health" in app_paths and "/ready" in app_paths, sorted(app_paths)
print("BUILT_IMAGE_OK=true")
PY

log "5. Остановка gateway и перезапуск только nails-api"
RUNTIME_MUTATED="true"
user_systemctl stop "$GATEWAY"
compose up -d --no-deps --force-recreate --no-build nails-api >/dev/null
wait_ready
RUNNING_SHA="$(
  compose exec -T nails-api \
    python -c 'import os; print(os.environ.get("NAILS_GIT_SHA", "unknown"))' \
    < /dev/null
)"
[[ "$RUNNING_SHA" == "$RELEASE_SHA" ]] || {
  echo "ERROR: running container SHA mismatch: ${RUNNING_SHA}" >&2
  exit 1
}

log "6. Установка plugins, skills и backup runtime из релизного дерева"
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

log "7. Старт gateway"
user_systemctl start "$GATEWAY"
