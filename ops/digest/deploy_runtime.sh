#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

MODE="${1:?usage: deploy_runtime.sh <snapshot|stop|install|restore> <runtime-backup> [source-ref]}"
RUNTIME_BACKUP="${2:?runtime backup directory is required}"
SOURCE_REF="${3:-origin/main}"

DIGEST_RUNTIME="/opt/nails/digest"
DIGEST_SERVICE="/etc/systemd/system/nails-finalization-digest.service"
DIGEST_TIMER="/etc/systemd/system/nails-finalization-digest.timer"
WORKTREE="${NAILS_DEPLOY_WORKTREE:-}"

snapshot() {
  [[ -d "$RUNTIME_BACKUP" ]]
  [[ -d "$DIGEST_RUNTIME" ]] && cp -a "$DIGEST_RUNTIME" "$RUNTIME_BACKUP/digest-runtime.before"
  [[ -f "$DIGEST_SERVICE" ]] && cp -a "$DIGEST_SERVICE" "$RUNTIME_BACKUP/digest-service.before"
  [[ -f "$DIGEST_TIMER" ]] && cp -a "$DIGEST_TIMER" "$RUNTIME_BACKUP/digest-timer.before"
  systemctl is-enabled nails-finalization-digest.timer \
    >"$RUNTIME_BACKUP/digest-timer-enabled.before" 2>/dev/null || true
  systemctl is-active nails-finalization-digest.timer \
    >"$RUNTIME_BACKUP/digest-timer-active.before" 2>/dev/null || true
}

stop_timer() {
  systemctl stop nails-finalization-digest.timer >/dev/null 2>&1 || true
}

restore() {
  stop_timer
  if [[ -d "$RUNTIME_BACKUP/digest-runtime.before" ]]; then
    rm -rf "$DIGEST_RUNTIME"
    cp -a "$RUNTIME_BACKUP/digest-runtime.before" "$DIGEST_RUNTIME"
  else
    rm -rf "$DIGEST_RUNTIME"
  fi
  if [[ -f "$RUNTIME_BACKUP/digest-service.before" ]]; then
    cp -a "$RUNTIME_BACKUP/digest-service.before" "$DIGEST_SERVICE"
  else
    rm -f "$DIGEST_SERVICE"
  fi
  if [[ -f "$RUNTIME_BACKUP/digest-timer.before" ]]; then
    cp -a "$RUNTIME_BACKUP/digest-timer.before" "$DIGEST_TIMER"
  else
    rm -f "$DIGEST_TIMER"
  fi
  systemctl daemon-reload
  if [[ "$(cat "$RUNTIME_BACKUP/digest-timer-enabled.before" 2>/dev/null)" == enabled ]]; then
    systemctl enable nails-finalization-digest.timer >/dev/null 2>&1
  else
    systemctl disable nails-finalization-digest.timer >/dev/null 2>&1 || true
  fi
  if [[ "$(cat "$RUNTIME_BACKUP/digest-timer-active.before" 2>/dev/null)" == active ]]; then
    systemctl start nails-finalization-digest.timer >/dev/null 2>&1
  fi
}

install_runtime() {
  [[ -n "$WORKTREE" && -d "$WORKTREE" ]]
  local source="$WORKTREE/ops/digest"
  python_bin="/usr/local/lib/hermes-agent/venv/bin/python"
  "$python_bin" -m py_compile "$source/send.py"
  systemd-analyze verify \
    "$source/nails-finalization-digest.service" \
    "$source/nails-finalization-digest.timer" >/dev/null

  rm -rf "$DIGEST_RUNTIME"
  install -d -o root -g root -m 700 "$DIGEST_RUNTIME"
  install -o root -g root -m 700 "$source/send.py" "$DIGEST_RUNTIME/send.py"
  install -o root -g root -m 644 \
    "$source/nails-finalization-digest.service" "$DIGEST_SERVICE"
  install -o root -g root -m 644 \
    "$source/nails-finalization-digest.timer" "$DIGEST_TIMER"
  systemctl daemon-reload

  if [[ "$SOURCE_REF" =~ ^origin/pr/[0-9]+$ ]]; then
    if [[ "$(cat "$RUNTIME_BACKUP/digest-timer-enabled.before" 2>/dev/null)" == enabled ]]; then
      systemctl enable nails-finalization-digest.timer >/dev/null 2>&1
    else
      systemctl disable nails-finalization-digest.timer >/dev/null 2>&1 || true
    fi
    if [[ "$(cat "$RUNTIME_BACKUP/digest-timer-active.before" 2>/dev/null)" == active ]]; then
      systemctl start nails-finalization-digest.timer >/dev/null 2>&1
    else
      systemctl stop nails-finalization-digest.timer >/dev/null 2>&1 || true
    fi
  else
    systemctl enable --now nails-finalization-digest.timer >/dev/null
    systemctl is-enabled --quiet nails-finalization-digest.timer
    systemctl is-active --quiet nails-finalization-digest.timer
  fi
}

case "$MODE" in
  snapshot) snapshot ;;
  stop) stop_timer ;;
  install) install_runtime ;;
  restore) restore ;;
  *) printf 'invalid digest runtime mode: %s\n' "$MODE" >&2; exit 2 ;;
esac
