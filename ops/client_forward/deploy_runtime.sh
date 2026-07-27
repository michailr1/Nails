#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

MODE="${1:?usage: deploy_runtime.sh <snapshot|stop|install|restore> <runtime-backup> [source-ref]}"
RUNTIME_BACKUP="${2:?runtime backup directory is required}"
SOURCE_REF="${3:-origin/main}"
WORKTREE="${NAILS_DEPLOY_WORKTREE:-}"

FORWARD_RUNTIME="/opt/nails/client-forward"
FORWARD_SERVICE="/etc/systemd/system/nails-client-forward.service"

snapshot() {
  [[ -d "$RUNTIME_BACKUP" ]]
  [[ -d "$FORWARD_RUNTIME" ]] && cp -a "$FORWARD_RUNTIME" "$RUNTIME_BACKUP/client-forward-runtime.before"
  [[ -f "$FORWARD_SERVICE" ]] && cp -a "$FORWARD_SERVICE" "$RUNTIME_BACKUP/client-forward-service.before"
  systemctl is-enabled nails-client-forward.service \
    >"$RUNTIME_BACKUP/client-forward-enabled.before" 2>/dev/null || true
  systemctl is-active nails-client-forward.service \
    >"$RUNTIME_BACKUP/client-forward-active.before" 2>/dev/null || true
}

stop_service() {
  systemctl stop nails-client-forward.service >/dev/null 2>&1 || true
}

restore() {
  stop_service
  if [[ -d "$RUNTIME_BACKUP/client-forward-runtime.before" ]]; then
    rm -rf "$FORWARD_RUNTIME"
    cp -a "$RUNTIME_BACKUP/client-forward-runtime.before" "$FORWARD_RUNTIME"
  else
    rm -rf "$FORWARD_RUNTIME"
  fi
  if [[ -f "$RUNTIME_BACKUP/client-forward-service.before" ]]; then
    cp -a "$RUNTIME_BACKUP/client-forward-service.before" "$FORWARD_SERVICE"
  else
    rm -f "$FORWARD_SERVICE"
  fi
  systemctl daemon-reload
  if [[ "$(cat "$RUNTIME_BACKUP/client-forward-enabled.before" 2>/dev/null)" == enabled ]]; then
    systemctl enable nails-client-forward.service >/dev/null 2>&1
  else
    systemctl disable nails-client-forward.service >/dev/null 2>&1 || true
  fi
  if [[ "$(cat "$RUNTIME_BACKUP/client-forward-active.before" 2>/dev/null)" == active ]]; then
    systemctl start nails-client-forward.service >/dev/null 2>&1
  fi
}

install_runtime() {
  [[ -n "$WORKTREE" && -d "$WORKTREE" ]]
  local source="$WORKTREE/ops/client_forward"
  local python_bin="/usr/local/lib/hermes-agent/venv/bin/python"
  "$python_bin" -m py_compile "$source/send.py"
  systemd-analyze verify "$source/nails-client-forward.service" >/dev/null

  rm -rf "$FORWARD_RUNTIME"
  install -d -o root -g root -m 700 "$FORWARD_RUNTIME"
  install -o root -g root -m 700 "$source/send.py" "$FORWARD_RUNTIME/send.py"
  install -o root -g root -m 644 "$source/nails-client-forward.service" "$FORWARD_SERVICE"
  systemctl daemon-reload

  if [[ "$SOURCE_REF" =~ ^origin/pr/[0-9]+$ ]]; then
    if [[ "$(cat "$RUNTIME_BACKUP/client-forward-enabled.before" 2>/dev/null)" == enabled ]]; then
      systemctl enable nails-client-forward.service >/dev/null 2>&1
    else
      systemctl disable nails-client-forward.service >/dev/null 2>&1 || true
    fi
    if [[ "$(cat "$RUNTIME_BACKUP/client-forward-active.before" 2>/dev/null)" == active ]]; then
      systemctl start nails-client-forward.service >/dev/null 2>&1
    else
      systemctl stop nails-client-forward.service >/dev/null 2>&1 || true
    fi
  else
    systemctl enable --now nails-client-forward.service >/dev/null
    systemctl is-enabled --quiet nails-client-forward.service
    systemctl is-active --quiet nails-client-forward.service
  fi
}

case "$MODE" in
  snapshot) snapshot ;;
  stop) stop_service ;;
  install) install_runtime ;;
  restore) restore ;;
  *) printf 'invalid client forward runtime mode: %s\n' "$MODE" >&2; exit 2 ;;
esac
