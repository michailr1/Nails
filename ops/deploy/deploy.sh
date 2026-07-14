#!/usr/bin/env bash
# Nails — единственный постоянный deploy-скрипт (см. docs/decisions/ADR-003).
#
# Использование: bash ops/deploy/deploy.sh <точный commit SHA из origin/main>
#
# Релиз всегда собирается из отдельного git worktree. SHA зашивается в образ и
# проверяется до остановки runtime и после запуска нового контейнера.

set -Eeuo pipefail
umask 077

RELEASE_SHA="${1:?usage: deploy.sh <exact-commit-sha-from-origin/main>}"
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: release must be an exact 40-character commit SHA" >&2
  exit 1
}

REPO="/opt/nails/repo"
BACKEND_ENV="/opt/nails/.env"
API_BASE="http://127.0.0.1:8210"
API_IMAGE="nails-nails-api:latest"
PROFILE="/root/.hermes/profiles/nails"
HERMES_BIN="/usr/local/lib/hermes-agent/venv/bin/hermes"
GATEWAY="hermes-gateway-nails.service"
USER_RUNTIME_DIR="/run/user/0"
BACKUP_ROOT="/opt/nails/backups"

PLUGINS=(nails_onboarding nails_scheduling)
SKILLS=(nails-onboarding nails-scheduling)

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
    log "rollback: restoring previous image, plugins, skills and gateway"
    compose up -d --no-deps --force-recreate --no-build nails-api >/dev/null 2>&1
    [[ -d "${RUNTIME_BACKUP}/plugins.before" ]] && {
      rm -rf "${PROFILE}/plugins"
      cp -a "${RUNTIME_BACKUP}/plugins.before" "${PROFILE}/plugins"
    }
    [[ -d "${RUNTIME_BACKUP}/skills.before" ]] && {
      rm -rf "${PROFILE}/skills"
      cp -a "${RUNTIME_BACKUP}/skills.before" "${PROFILE}/skills"
    }
    user_systemctl start "$GATEWAY" >/dev/null 2>&1
    printf 'DEPLOY_ROLLED_BACK=true prev_sha=%s\n' "$PREV_SHA"
  else
    printf 'DEPLOY_ROLLED_BACK=false\n'
  fi

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
[[ "$(id -u)" -eq 0 ]]
[[ "$(hostname -f)" == "de.funti.cc" ]]
[[ -f "$BACKEND_ENV" ]]
[[ "$(git -C "$REPO" branch --show-current)" == "main" ]]
[[ -z "$(git -C "$REPO" status --porcelain)" ]]
git -C "$REPO" fetch origin main
[[ "$(git -C "$REPO" rev-parse origin/main)" =~ ^[0-9a-f]{40}$ ]]
git -C "$REPO" cat-file -e "${RELEASE_SHA}^{commit}"
git -C "$REPO" merge-base --is-ancestor "$RELEASE_SHA" origin/main || {
  echo "ERROR: SHA is not on origin/main" >&2
  exit 1
}
PREV_SHA="$(git -C "$REPO" rev-parse HEAD)"
printf 'prev_sha=%s release_sha=%s\n' "$PREV_SHA" "$RELEASE_SHA"

log "1. Точное дерево релиза"
git -C "$REPO" worktree add --detach "$WORKTREE" "$RELEASE_SHA" >/dev/null
[[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$RELEASE_SHA" ]]

log "2. Бэкапы базы и runtime"
install -d -m 700 "$BACKUP_ROOT" "$RUNTIME_BACKUP"
compose exec -T nails-db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip -9 >"$DB_BACKUP"
chmod 600 "$DB_BACKUP"
[[ -s "$DB_BACKUP" ]]
gzip -t "$DB_BACKUP"
cp -a "${PROFILE}/plugins" "${RUNTIME_BACKUP}/plugins.before"
cp -a "${PROFILE}/skills" "${RUNTIME_BACKUP}/skills.before"

log "3. Сборка образа из точного дерева"
docker image tag "$API_IMAGE" "$ROLLBACK_IMAGE"
compose build --build-arg GIT_SHA="$RELEASE_SHA" nails-api >/dev/null
IMAGE_RETAGGED="true"

log "4. Проверка собранного образа ДО остановки runtime"
docker run --rm --network none --read-only --tmpfs /tmp:size=16m \
  -e EXPECTED_SHA="$RELEASE_SHA" \
  -e APP_TIMEZONE=UTC \
  -e DATABASE_URL=postgresql+psycopg://smoke:smoke@127.0.0.1:5432/smoke \
  -e INTERNAL_API_KEY=deploy-smoke-key-0000000000000000 \
  "$API_IMAGE" python - <<'PY'
import os

expected = os.environ["EXPECTED_SHA"]
actual = os.environ.get("NAILS_GIT_SHA", "unknown")
assert actual == expected, f"image built from wrong tree: {actual!r} != {expected!r}"

from app.main import app

paths = {getattr(route, "path", "") for route in app.routes}
assert any(path.startswith("/api/v1/") for path in paths), sorted(paths)
print("BUILT_IMAGE_OK=true")
PY

log "5. Остановка gateway и перезапуск только nails-api"
RUNTIME_MUTATED="true"
user_systemctl stop "$GATEWAY"
compose up -d --no-deps --force-recreate --no-build nails-api >/dev/null
wait_ready
RUNNING_SHA="$(compose exec -T nails-api python -c 'import os; print(os.environ.get("NAILS_GIT_SHA", "unknown"))')"
[[ "$RUNNING_SHA" == "$RELEASE_SHA" ]] || {
  echo "ERROR: running container SHA mismatch: ${RUNNING_SHA}" >&2
  exit 1
}

log "6. Установка plugins и skills из релизного дерева"
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

log "7. Старт gateway"
user_systemctl start "$GATEWAY"
for _ in $(seq 1 60); do
  user_systemctl is-active --quiet "$GATEWAY" && break
  sleep 1
done
user_systemctl is-active --quiet "$GATEWAY"

log "8. Фиксация checkout репозитория"
git -C "$REPO" worktree remove --force "$WORKTREE"
git -C "$REPO" checkout main >/dev/null 2>&1
if git -C "$REPO" merge-base --is-ancestor "$PREV_SHA" "$RELEASE_SHA"; then
  git -C "$REPO" merge --ff-only "$RELEASE_SHA" >/dev/null
else
  git -C "$REPO" reset --hard "$RELEASE_SHA" >/dev/null
fi
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$RELEASE_SHA" ]]
[[ -z "$(git -C "$REPO" status --porcelain)" ]]

docker image rm "$ROLLBACK_IMAGE" >/dev/null 2>&1 || true
trap - ERR

printf 'DEPLOY_OK=true sha=%s prev_sha=%s db_backup=%s\n' \
  "$RELEASE_SHA" "$PREV_SHA" "$DB_BACKUP"
