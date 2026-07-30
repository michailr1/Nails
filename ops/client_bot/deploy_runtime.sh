#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

MODE="${1:?usage: deploy_runtime.sh <snapshot|stop|install|restore> <runtime-backup> [source-ref]}"
RUNTIME_BACKUP="${2:?runtime backup directory is required}"
SOURCE_REF="${3:-origin/main}"
WORKTREE="${NAILS_DEPLOY_WORKTREE:-}"
DESIRED_ACTIVE="${NAILS_CLIENT_BOT_DESIRED_ACTIVE:-preserve}"

SERVICE_PATH="/etc/systemd/system/nails-client-bot.service"
STATUS_PATH="/run/nails/client-bot-status.json"

[[ "$DESIRED_ACTIVE" == "preserve" || "$DESIRED_ACTIVE" == "true" || "$DESIRED_ACTIVE" == "false" ]] || {
  printf 'invalid NAILS_CLIENT_BOT_DESIRED_ACTIVE: %s\n' "$DESIRED_ACTIVE" >&2
  exit 2
}

snapshot() {
  [[ -d "$RUNTIME_BACKUP" ]]
  [[ -f "$SERVICE_PATH" ]] && cp -a "$SERVICE_PATH" "$RUNTIME_BACKUP/client-bot-service.before"
  systemctl is-enabled nails-client-bot.service >"$RUNTIME_BACKUP/client-bot-enabled.before" 2>/dev/null || true
  systemctl is-active nails-client-bot.service >"$RUNTIME_BACKUP/client-bot-active.before" 2>/dev/null || true
}

stop_service() {
  systemctl stop nails-client-bot.service >/dev/null 2>&1 || true
}

restore() {
  stop_service
  if [[ -f "$RUNTIME_BACKUP/client-bot-service.before" ]]; then
    cp -a "$RUNTIME_BACKUP/client-bot-service.before" "$SERVICE_PATH"
  else
    rm -f "$SERVICE_PATH"
  fi
  rm -f "$STATUS_PATH"
  systemctl daemon-reload
  if [[ "$(cat "$RUNTIME_BACKUP/client-bot-enabled.before" 2>/dev/null)" == enabled ]]; then
    systemctl enable nails-client-bot.service >/dev/null 2>&1
  else
    systemctl disable nails-client-bot.service >/dev/null 2>&1 || true
  fi
  if [[ "$(cat "$RUNTIME_BACKUP/client-bot-active.before" 2>/dev/null)" == active ]]; then
    systemctl start nails-client-bot.service >/dev/null 2>&1
  fi
}

apply_desired_state() {
  local desired="$1"
  if [[ "$desired" == "true" ]]; then
    systemctl enable --now nails-client-bot.service >/dev/null
    systemctl is-enabled --quiet nails-client-bot.service
    systemctl is-active --quiet nails-client-bot.service
    return
  fi
  if [[ "$desired" == "false" ]]; then
    systemctl disable --now nails-client-bot.service >/dev/null 2>&1 || true
    rm -f "$STATUS_PATH"
    return
  fi

  if [[ "$SOURCE_REF" =~ ^origin/pr/[0-9]+$ ]]; then
    if [[ "$(cat "$RUNTIME_BACKUP/client-bot-enabled.before" 2>/dev/null)" == enabled ]]; then
      systemctl enable nails-client-bot.service >/dev/null 2>&1
    else
      systemctl disable nails-client-bot.service >/dev/null 2>&1 || true
    fi
    if [[ "$(cat "$RUNTIME_BACKUP/client-bot-active.before" 2>/dev/null)" == active ]]; then
      systemctl start nails-client-bot.service >/dev/null 2>&1
    else
      systemctl stop nails-client-bot.service >/dev/null 2>&1 || true
    fi
  fi
}

install_runtime() {
  [[ -n "$WORKTREE" && -d "$WORKTREE" ]]
  local source="$WORKTREE/ops/client_bot"
  local python_bin="/usr/local/lib/hermes-agent/venv/bin/python"
  "$python_bin" -m py_compile \
    "$WORKTREE/backend/app/client_bot_v1.py" \
    "$WORKTREE/backend/app/client_bot_outbox.py"
  systemd-analyze verify "$source/nails-client-bot.service" >/dev/null
  install -o root -g root -m 644 "$source/nails-client-bot.service" "$SERVICE_PATH"
  systemctl daemon-reload
  apply_desired_state "$DESIRED_ACTIVE"
}

case "$MODE" in
  snapshot) snapshot ;;
  stop) stop_service ;;
  install) install_runtime ;;
  restore) restore ;;
  *) printf 'invalid client bot runtime mode: %s\n' "$MODE" >&2; exit 2 ;;
esac
