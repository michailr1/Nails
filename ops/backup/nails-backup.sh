#!/usr/bin/env bash
# Nails PostgreSQL backup, restore verification and retention.

set -Eeuo pipefail
umask 077

MODE="${1:-daily}"
REPO="${NAILS_REPO:-/opt/nails/repo}"
BACKEND_ENV="${NAILS_BACKEND_ENV:-/opt/nails/.env}"
BACKUP_ENV="${NAILS_BACKUP_ENV:-/opt/nails/backup.env}"
PROFILE_ENV="${NAILS_PROFILE_ENV:-/root/.hermes/profiles/nails/.env}"
BACKUP_ROOT="${NAILS_BACKUP_ROOT:-/opt/nails/backups}"
MAX_TELEGRAM_BYTES="${NAILS_BACKUP_TELEGRAM_MAX_BYTES:-15728640}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DAILY_BACKUP="${BACKUP_ROOT}/nails-daily-${STAMP}.sql.gz"
RESTORE_DB="nails_restore_${STAMP,,}"
RESTORE_DB="${RESTORE_DB//[^a-z0-9_]/_}"
RESTORE_ACTIVE=false

log() { printf '== nails-backup: %s ==\n' "$*"; }
die() { printf 'BACKUP_FAILED: %s\n' "$*" >&2; exit 1; }
compose() {
  docker compose \
    --project-directory "$REPO" \
    --file "$REPO/compose.yaml" \
    --env-file "$BACKEND_ENV" \
    "$@"
}
read_env_value() {
  local file="$1" key="$2" value
  [[ -f "$file" ]] || return 1
  value="$(sed -n "s/^${key}=//p" "$file" | tail -n 1)"
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  [[ -n "$value" ]] || return 1
  printf '%s' "$value"
}

drop_restore_db() {
  compose exec -T nails-db sh -c \
    'dropdb --if-exists --force -U "$POSTGRES_USER" "$1"' sh "$RESTORE_DB" \
    < /dev/null >/dev/null 2>&1 || true
  RESTORE_ACTIVE=false
}
cleanup() {
  if [[ "$RESTORE_ACTIVE" == "true" ]]; then
    drop_restore_db
  fi
}
trap cleanup EXIT

verify_restore() {
  local archive="$1" table_count alembic_revision
  gzip -t "$archive"
  drop_restore_db
  compose exec -T nails-db sh -c \
    'createdb -U "$POSTGRES_USER" "$1"' sh "$RESTORE_DB" < /dev/null
  RESTORE_ACTIVE=true
  gzip -dc "$archive" | compose exec -T nails-db sh -c \
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"' sh "$RESTORE_DB" >/dev/null
  table_count="$(compose exec -T nails-db sh -c \
    'psql -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -c "select count(*) from information_schema.tables where table_schema = '\''public'\'';"' \
    sh "$RESTORE_DB" < /dev/null | tr -d '\r')"
  alembic_revision="$(compose exec -T nails-db sh -c \
    'psql -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -c "select version_num from alembic_version;"' \
    sh "$RESTORE_DB" < /dev/null | tr -d '\r')"
  [[ "$table_count" =~ ^[1-9][0-9]*$ ]] || die "restored public schema is empty"
  [[ -n "$alembic_revision" ]] || die "restored alembic revision is empty"
  printf 'RESTORE_TEST_OK=true tables=%s alembic=%s\n' "$table_count" "$alembic_revision"
  drop_restore_db
}

promote_generations() {
  local archive="$1" weekday monthday week month
  weekday="$(date -u +%u)"; monthday="$(date -u +%d)"
  week="$(date -u +%G-W%V)"; month="$(date -u +%Y-%m)"
  if [[ "$weekday" == "7" ]]; then
    cp -f "$archive" "${BACKUP_ROOT}/nails-weekly-${week}.sql.gz"
  fi
  if [[ "$monthday" == "01" ]]; then
    cp -f "$archive" "${BACKUP_ROOT}/nails-monthly-${month}.sql.gz"
  fi
}

rotate_files() {
  find "$BACKUP_ROOT" -maxdepth 1 -type f -name 'nails-daily-*.sql.gz' -mtime +4 -delete
  find "$BACKUP_ROOT" -maxdepth 1 -type f -name 'nails-weekly-*.sql.gz' -mtime +20 -delete
  find "$BACKUP_ROOT" -maxdepth 1 -type f -name 'nails-monthly-*.sql.gz' -mtime +365 -delete
  find "$BACKUP_ROOT" -maxdepth 1 -type f -name '*.log' -mtime +13 -delete
}

send_telegram() {
  local archive="$1" size token chat_id
  size="$(stat -c '%s' "$archive")"
  if (( size > MAX_TELEGRAM_BYTES )); then
    printf 'TELEGRAM_BACKUP_SKIPPED=true reason=size_limit bytes=%s\n' "$size"
    return 0
  fi
  token="$(read_env_value "$PROFILE_ENV" TELEGRAM_BOT_TOKEN)" || die "Telegram token is missing"
  chat_id="$(read_env_value "$BACKUP_ENV" NAILS_BACKUP_TELEGRAM_CHAT_ID)" || die "Telegram backup chat ID is missing"
  curl --fail --silent --show-error \
    -F "chat_id=${chat_id}" \
    -F "caption=Nails verified backup ${STAMP}" \
    -F "document=@${archive}" \
    "https://api.telegram.org/bot${token}/sendDocument" >/dev/null
  printf 'TELEGRAM_BACKUP_SENT=true bytes=%s\n' "$size"
}

[[ "$MODE" == "daily" || "$MODE" == "verify" || "$MODE" == "rotate" ]] || \
  die "usage: nails-backup.sh daily|verify <archive>|rotate"
if [[ "$MODE" != "rotate" || "${NAILS_BACKUP_TEST_MODE:-false}" != "true" ]]; then
  [[ "$(id -u)" -eq 0 ]] || die "root is required"
fi
install -d -m 700 "$BACKUP_ROOT"
if [[ "$MODE" != "rotate" ]]; then
  [[ -f "$REPO/compose.yaml" ]] || die "repository compose.yaml is missing"
  [[ -f "$BACKEND_ENV" ]] || die "backend env is missing"
fi

case "$MODE" in
  daily)
    log "create compressed PostgreSQL dump"
    compose exec -T nails-db sh -c \
      'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' < /dev/null | gzip -9 >"$DAILY_BACKUP"
    [[ -s "$DAILY_BACKUP" ]] || die "backup is empty"
    chmod 600 "$DAILY_BACKUP"
    log "verify isolated restore"
    verify_restore "$DAILY_BACKUP"
    promote_generations "$DAILY_BACKUP"
    rotate_files
    send_telegram "$DAILY_BACKUP"
    printf 'DAILY_BACKUP_OK=true archive=%s bytes=%s\n' \
      "$DAILY_BACKUP" "$(stat -c '%s' "$DAILY_BACKUP")"
    ;;
  verify)
    [[ $# -eq 2 && -f "$2" ]] || die "verify requires an existing archive"
    verify_restore "$2"
    ;;
  rotate)
    rotate_files
    printf 'BACKUP_ROTATION_OK=true\n'
    ;;
esac
