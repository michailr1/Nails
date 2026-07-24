#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ACTION="${1:-install}"
SOURCE_ROOT="${NAILS_RELEASE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
RUNTIME_DIR="/opt/nails/hermes-access"
SERVICE_FILE="/etc/systemd/system/nails-hermes-access.service"
BACKEND_ENV="/opt/nails/.env"
GROUP_NAME="nails-hermes-access"
GROUP_GID="42891"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/opt/nails/backups/hermes-access-${STAMP}"

fail() { printf 'HERMES_ACCESS_INSTALL_FAILED: %s\n' "$*" >&2; exit 1; }
[[ "$(id -u)" -eq 0 ]] || fail "root is required"

set_env_key() {
  local key="$1" value="$2" file="$3" tmp
  tmp="$(mktemp "${file}.XXXXXX")"
  awk -v key="$key" -v value="$value" '
    BEGIN { done=0 }
    index($0, key "=") == 1 {
      if (!done) print key "=" value
      done=1
      next
    }
    { print }
    END { if (!done) print key "=" value }
  ' "$file" >"$tmp"
  chmod --reference="$file" "$tmp"
  chown --reference="$file" "$tmp"
  mv "$tmp" "$file"
}

case "$ACTION" in
  install)
    [[ -f "$SOURCE_ROOT/ops/hermes_access/helper.py" ]] || fail "helper source missing"
    [[ -f "$SOURCE_ROOT/ops/hermes_access/nails-hermes-access.service" ]] || fail "service source missing"
    [[ -f "$BACKEND_ENV" ]] || fail "backend env missing"
    getent group "$GROUP_NAME" >/dev/null || groupadd --system --gid "$GROUP_GID" "$GROUP_NAME"
    [[ "$(getent group "$GROUP_NAME" | cut -d: -f3)" == "$GROUP_GID" ]] || fail "unexpected helper group gid"

    install -d -m 700 "$BACKUP_DIR"
    [[ -f "$RUNTIME_DIR/helper.py" ]] && cp -a "$RUNTIME_DIR/helper.py" "$BACKUP_DIR/helper.py.before"
    [[ -f "$SERVICE_FILE" ]] && cp -a "$SERVICE_FILE" "$BACKUP_DIR/service.before"
    cp -a "$BACKEND_ENV" "$BACKUP_DIR/backend.env.before"

    install -d -o root -g root -m 700 "$RUNTIME_DIR"
    install -o root -g root -m 700 "$SOURCE_ROOT/ops/hermes_access/helper.py" "$RUNTIME_DIR/helper.py"
    install -o root -g root -m 644 "$SOURCE_ROOT/ops/hermes_access/nails-hermes-access.service" "$SERVICE_FILE"
    set_env_key HERMES_ACCESS_SYNC_ENABLED true "$BACKEND_ENV"
    set_env_key HERMES_ACCESS_SOCKET /run/nails-hermes-access/access.sock "$BACKEND_ENV"
    set_env_key HERMES_ACCESS_TIMEOUT_SECONDS 10 "$BACKEND_ENV"

    /usr/bin/python3 -m py_compile "$RUNTIME_DIR/helper.py"
    systemd-analyze verify "$SERVICE_FILE" >/dev/null
    systemctl daemon-reload
    systemctl enable --now nails-hermes-access.service >/dev/null
    systemctl is-active --quiet nails-hermes-access.service
    [[ -S /run/nails-hermes-access/access.sock ]] || fail "helper socket missing"
    [[ "$(stat -c %g /run/nails-hermes-access/access.sock)" == "$GROUP_GID" ]] || fail "helper socket gid mismatch"
    printf 'HERMES_ACCESS_INSTALL_OK=true backup=%s\n' "$BACKUP_DIR"
    ;;
  restore)
    backup="${2:?usage: install.sh restore <backup-dir>}"
    [[ -d "$backup" ]] || fail "backup missing"
    systemctl disable --now nails-hermes-access.service >/dev/null 2>&1 || true
    if [[ -f "$backup/helper.py.before" ]]; then
      install -d -o root -g root -m 700 "$RUNTIME_DIR"
      cp -a "$backup/helper.py.before" "$RUNTIME_DIR/helper.py"
    else
      rm -rf "$RUNTIME_DIR"
    fi
    if [[ -f "$backup/service.before" ]]; then
      cp -a "$backup/service.before" "$SERVICE_FILE"
    else
      rm -f "$SERVICE_FILE"
    fi
    cp -a "$backup/backend.env.before" "$BACKEND_ENV"
    systemctl daemon-reload
    [[ -f "$SERVICE_FILE" ]] && systemctl enable --now nails-hermes-access.service >/dev/null
    printf 'HERMES_ACCESS_RESTORE_OK=true backup=%s\n' "$backup"
    ;;
  *) fail "action must be install or restore" ;;
esac
