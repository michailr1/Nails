#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

die() {
  printf 'PRECONDITION_FAILED: %s\n' "$*" >&2
  exit 1
}

[[ -f "${BASH_SOURCE[0]}" ]] || die "candidate adapter must be executed from a regular file"
[[ $# -eq 1 ]] || die "usage: NAILS_CANDIDATE_ENV=/absolute/path <candidate-adapter> <exact-sha>"

SHA="$1"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || die "exact SHA must contain 40 lowercase hexadecimal characters"
ACTION="${NAILS_CANDIDATE_ACTION:-up}"
[[ "$ACTION" == up || "$ACTION" == status || "$ACTION" == down ]] || die "NAILS_CANDIDATE_ACTION must be up, status, or down"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
COMPOSE_FILE="$REPO_ROOT/compose.yaml"
[[ -f "$COMPOSE_FILE" ]] || die "compose.yaml is missing from the exact candidate tree"
actual_sha="$(git -C "$REPO_ROOT" rev-parse HEAD)"
[[ "$actual_sha" == "$SHA" ]] || die "candidate tree SHA $actual_sha does not match requested $SHA"
[[ -z "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=no)" ]] || die "candidate tree must be clean"

CANDIDATE_ENV="${NAILS_CANDIDATE_ENV:-}"
[[ -n "$CANDIDATE_ENV" ]] || die "NAILS_CANDIDATE_ENV is required"
[[ "$CANDIDATE_ENV" == /* ]] || die "NAILS_CANDIDATE_ENV must be an absolute path"
[[ "$CANDIDATE_ENV" != "/opt/nails/.env" ]] || die "candidate env must not be the production env"
[[ -f "$CANDIDATE_ENV" && ! -L "$CANDIDATE_ENV" ]] || die "candidate env must be a regular non-symlink file"
mode="$(stat -c '%a' "$CANDIDATE_ENV")"
(( (8#$mode & 8#077) == 0 )) || die "candidate env must not be accessible by group or others"

read_env_value() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "$CANDIDATE_ENV" | tail -n 1 || true)"
  [[ -n "$line" ]] || return 1
  printf '%s' "${line#*=}" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

api_port="$(read_env_value NAILS_API_PORT || true)"
web_port="$(read_env_value NAILS_WEB_PORT || true)"
database_url="$(read_env_value DATABASE_URL || true)"
client_bot_enabled="$(read_env_value CLIENT_BOT_ENABLED || printf 'false')"
hermes_sync_enabled="$(read_env_value HERMES_ACCESS_SYNC_ENABLED || printf 'false')"

[[ "$api_port" =~ ^[0-9]+$ && "$api_port" -ge 1024 && "$api_port" -le 65535 ]] || die "candidate NAILS_API_PORT must be an unprivileged TCP port"
[[ "$web_port" =~ ^[0-9]+$ && "$web_port" -ge 1024 && "$web_port" -le 65535 ]] || die "candidate NAILS_WEB_PORT must be an unprivileged TCP port"
[[ "$api_port" != 8210 ]] || die "candidate API port must not be the production port"
[[ "$web_port" != 8220 ]] || die "candidate web port must not be the production port"
[[ "$api_port" != "$web_port" ]] || die "candidate API and web ports must differ"
[[ "$database_url" == *"@nails-db:5432/"* ]] || die "candidate DATABASE_URL must target the isolated nails-db service"
[[ "$database_url" != *"127.0.0.1"* && "$database_url" != *"localhost"* ]] || die "candidate DATABASE_URL must not target a host database"
[[ "$client_bot_enabled" == false ]] || die "candidate client bot must be disabled"
[[ "$hermes_sync_enabled" == false ]] || die "candidate Hermes access sync must be disabled"

suffix="${SHA:0:12}"
project="nails-candidate-${suffix}"
volume="${project}-postgres"
edge_network="${project}-edge"
internal_network="${project}-internal"

compose() {
  NAILS_COMPOSE_PROJECT_NAME="$project" \
  NAILS_POSTGRES_VOLUME_NAME="$volume" \
  NAILS_EDGE_NETWORK_NAME="$edge_network" \
  NAILS_INTERNAL_NETWORK_NAME="$internal_network" \
  docker compose --env-file "$CANDIDATE_ENV" -f "$COMPOSE_FILE" -p "$project" "$@"
}

production_ids_before="$(docker ps -aq --filter 'name=^/nails-nails-')"
production_volume_before="$(docker volume inspect -f '{{.Name}}' nails-postgres-data 2>/dev/null || true)"

verify_production_unchanged() {
  local production_ids_after production_volume_after
  production_ids_after="$(docker ps -aq --filter 'name=^/nails-nails-')"
  production_volume_after="$(docker volume inspect -f '{{.Name}}' nails-postgres-data 2>/dev/null || true)"
  [[ "$production_ids_after" == "$production_ids_before" ]] || die "production container set changed during candidate action"
  [[ "$production_volume_after" == "$production_volume_before" ]] || die "production database volume changed during candidate action"
}

if [[ "$ACTION" == down ]]; then
  compose down --volumes --remove-orphans
  verify_production_unchanged
  printf 'candidate_action=down\n'
  printf 'candidate_project=%s\n' "$project"
  printf 'candidate_cleanup_ok=true\n'
  printf 'production_runtime_unchanged=true\n'
  printf 'production_db_unchanged=true\n'
  exit 0
fi

if [[ "$ACTION" == status ]]; then
  compose ps
  verify_production_unchanged
  printf 'candidate_action=status\n'
  printf 'candidate_project=%s\n' "$project"
  printf 'candidate_api_url=http://127.0.0.1:%s\n' "$api_port"
  printf 'candidate_web_url=http://127.0.0.1:%s\n' "$web_port"
  printf 'production_runtime_unchanged=true\n'
  printf 'production_db_unchanged=true\n'
  exit 0
fi

failed=true
cleanup_failed_up() {
  local status=$?
  if [[ "$failed" == true ]]; then
    set +e
    compose down --volumes --remove-orphans >/dev/null 2>&1
  fi
  return "$status"
}
trap cleanup_failed_up EXIT

diagnose_start_failure() {
  printf 'candidate_start_diagnostics_begin=true\n' >&2
  compose ps -a >&2 || true
  compose logs --no-color --tail 200 nails-db nails-api >&2 || true
  printf 'candidate_start_diagnostics_end=true\n' >&2
}

[[ -z "$(docker ps -aq --filter "label=com.docker.compose.project=$project")" ]] || die "candidate project already exists; run candidate down first"
[[ -z "$(docker volume ls -q --filter "name=^${volume}$")" ]] || die "candidate volume already exists; run candidate down first"

if ! compose up -d --build --wait nails-db nails-api nails-web; then
  diagnose_start_failure
  die "candidate compose startup failed; diagnostics emitted before cleanup"
fi

api_health="$(curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:${api_port}/health")"
api_readiness="$(curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:${api_port}/ready")"
web_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 "http://127.0.0.1:${web_port}/")"
[[ -n "$api_health" ]] || die "candidate API health response is empty"
[[ -n "$api_readiness" ]] || die "candidate API readiness response is empty"
[[ "$web_status" == 200 ]] || die "candidate web returned HTTP $web_status"

candidate_db_id="$(compose ps -q nails-db)"
candidate_api_id="$(compose ps -q nails-api)"
candidate_web_id="$(compose ps -q nails-web)"
[[ -n "$candidate_db_id" && -n "$candidate_api_id" && -n "$candidate_web_id" ]] || die "candidate isolated runtime is incomplete"
[[ -z "$(compose ps -q nails-client-bot)" ]] || die "candidate client bot must not be created"

verify_production_unchanged
failed=false
printf 'CANDIDATE_RUNTIME_OK=true\n'
printf 'candidate_action=up\n'
printf 'candidate_sha=%s\n' "$SHA"
printf 'candidate_project=%s\n' "$project"
printf 'candidate_volume=%s\n' "$volume"
printf 'candidate_edge_network=%s\n' "$edge_network"
printf 'candidate_internal_network=%s\n' "$internal_network"
printf 'candidate_db_container=%s\n' "$candidate_db_id"
printf 'candidate_api_container=%s\n' "$candidate_api_id"
printf 'candidate_web_container=%s\n' "$candidate_web_id"
printf 'candidate_api_url=http://127.0.0.1:%s\n' "$api_port"
printf 'candidate_web_url=http://127.0.0.1:%s\n' "$web_port"
printf 'candidate_client_bot_created=false\n'
printf 'candidate_db_isolated=true\n'
printf 'candidate_runtime_isolated=true\n'
printf 'production_runtime_unchanged=true\n'
printf 'production_db_unchanged=true\n'
