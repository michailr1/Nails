#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO=/opt/nails/repo
BACKEND_ENV=/opt/nails/.env
PROFILE_ENV=/root/.hermes/profiles/nails/.env
BACKUP_RUNTIME=/opt/nails/backup
ROOT=/opt/nails/backups
DAILY="$ROOT/daily"
WEEKLY="$ROOT/weekly"
MONTHLY="$ROOT/monthly"
STATUS="$ROOT/status"
LOG="$ROOT/logs/backup.log"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WEEK="$(date -u +%G-W%V)"
MONTH="${STAMP:0:6}"
DUMP="$DAILY/nails-${STAMP}.sql.gz"
RESTORE_DB="nails_restore_${STAMP,,}_$$"
RESTORE_DB="${RESTORE_DB//[^a-z0-9_]/_}"
TEMP_CREATED=false

mkdir -p "$DAILY" "$WEEKLY" "$MONTHLY" "$STATUS" "$(dirname "$LOG")"
chmod 700 "$ROOT" "$DAILY" "$WEEKLY" "$MONTHLY" "$STATUS" "$(dirname "$LOG")"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
compose() {
  docker compose --project-directory "$REPO" --file "$REPO/compose.yaml" \
    --env-file "$BACKEND_ENV" "$@"
}
cleanup() {
  if [[ "$TEMP_CREATED" == true ]]; then
    compose exec -T nails-db sh -c \
      'dropdb --if-exists --force -U "$POSTGRES_USER" "$1"' sh "$RESTORE_DB" \
      </dev/null >/dev/null 2>&1 || true
  fi
}
on_error() {
  local code=$?
  trap - ERR
  cleanup
  printf 'failed_at=%s exit_code=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$code" \
    >"$STATUS/last-failure"
  log "BACKUP_FAILED exit_code=$code"
  exit "$code"
}
trap cleanup EXIT
trap on_error ERR

[[ "$(id -u)" -eq 0 ]]
[[ "$(hostname -f)" == de.funti.cc ]]
[[ -f "$BACKEND_ENV" && -f "$PROFILE_ENV" && -x "$BACKUP_RUNTIME/retention.py" ]]

log "backup start"
compose exec -T nails-db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  </dev/null | gzip -9 >"$DUMP"
chmod 600 "$DUMP"
[[ -s "$DUMP" ]]
gzip -t "$DUMP"

SOURCE_COUNTS="$(compose exec -T nails-db sh -c '
  psql -XAt -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT tablename || E'\''\t'\'' || (xpath('\''/row/c/text()'\'', query_to_xml(format('\''SELECT count(*) AS c FROM %I'\'', tablename), false, true, '\'''\'')))[1]::text FROM pg_tables WHERE schemaname='\''public'\'' ORDER BY tablename"
' </dev/null)"
SOURCE_ALEMBIC="$(compose exec -T nails-db sh -c '
  psql -XAt -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT version_num FROM alembic_version"
' </dev/null)"
[[ -n "$SOURCE_COUNTS" && -n "$SOURCE_ALEMBIC" ]]

compose exec -T nails-db sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$RESTORE_DB" </dev/null
TEMP_CREATED=true
gzip -dc "$DUMP" | compose exec -T nails-db sh -c \
  'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"' sh "$RESTORE_DB" \
  </dev/null >/dev/null

RESTORE_COUNTS="$(compose exec -T nails-db sh -c '
  psql -XAt -U "$POSTGRES_USER" -d "$1" -c \
  "SELECT tablename || E'\''\t'\'' || (xpath('\''/row/c/text()'\'', query_to_xml(format('\''SELECT count(*) AS c FROM %I'\'', tablename), false, true, '\'''\'')))[1]::text FROM pg_tables WHERE schemaname='\''public'\'' ORDER BY tablename"
' sh "$RESTORE_DB" </dev/null)"
RESTORE_ALEMBIC="$(compose exec -T nails-db sh -c '
  psql -XAt -U "$POSTGRES_USER" -d "$1" -c "SELECT version_num FROM alembic_version"
' sh "$RESTORE_DB" </dev/null)"
[[ "$RESTORE_COUNTS" == "$SOURCE_COUNTS" ]]
[[ "$RESTORE_ALEMBIC" == "$SOURCE_ALEMBIC" ]]
cleanup
TEMP_CREATED=false

cp -f "$DUMP" "$WEEKLY/nails-${WEEK}.sql.gz"
cp -f "$DUMP" "$MONTHLY/nails-${MONTH}.sql.gz"
chmod 600 "$WEEKLY/nails-${WEEK}.sql.gz" "$MONTHLY/nails-${MONTH}.sql.gz"

python3 "$BACKUP_RUNTIME/retention.py" --apply --root "$ROOT" \
  --runtime-root /root/.hermes/profiles/nails/backups

readarray -t TG < <(python3 - "$PROFILE_ENV" <<'PY'
import re, sys
values = {}
for line in open(sys.argv[1], encoding="utf-8"):
    match = re.match(r"^(TELEGRAM_BOT_TOKEN|TELEGRAM_TOKEN|NAILS_BACKUP_TELEGRAM_CHAT_ID)=(.*)$", line.strip())
    if match:
        values[match.group(1)] = match.group(2).strip().strip('"').strip("'")
print(values.get("TELEGRAM_BOT_TOKEN") or values.get("TELEGRAM_TOKEN") or "")
print(values.get("NAILS_BACKUP_TELEGRAM_CHAT_ID") or "")
PY
)
TOKEN="${TG[0]:-}"
CHAT_ID="${TG[1]:-}"
[[ -n "$TOKEN" && -n "$CHAT_ID" ]]
SIZE="$(stat -c %s "$DUMP")"
[[ "$SIZE" -le 15728640 ]]
RESPONSE="$(curl -fsS --max-time 120 \
  -F "chat_id=$CHAT_ID" -F "document=@$DUMP" \
  -F "caption=Nails verified backup $STAMP" \
  "https://api.telegram.org/bot${TOKEN}/sendDocument")"
grep -q '"ok":true' <<<"$RESPONSE"

DISK_PERCENT="$(df -P "$ROOT" | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
[[ "$DISK_PERCENT" =~ ^[0-9]+$ ]]
if (( DISK_PERCENT >= 90 )); then
  log "DISK_CRITICAL percent=$DISK_PERCENT"
  exit 1
elif (( DISK_PERCENT >= 80 )); then
  log "DISK_WARNING percent=$DISK_PERCENT"
fi

printf 'completed_at=%s\nbackup=%s\nalembic=%s\ndisk_percent=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$DUMP" "$SOURCE_ALEMBIC" "$DISK_PERCENT" \
  >"$STATUS/last-success"
rm -f "$STATUS/last-failure"
log "BACKUP_OK backup=$DUMP alembic=$SOURCE_ALEMBIC disk_percent=$DISK_PERCENT"
