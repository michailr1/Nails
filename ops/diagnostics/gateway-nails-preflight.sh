#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

RUNBOOK_ID="NAILS-GATEWAY-PREFLIGHT-DIAGNOSTIC"
EXPECTED_HOST="de.funti.cc"
REPO="/opt/nails/repo"
PROFILE="/root/.hermes/profiles/nails"
PROFILE_ENV="${PROFILE}/.env"
GATEWAY="hermes-gateway-nails.service"
API_BASE="http://127.0.0.1:8210"
DIAGNOSTIC_SHA="${NAILS_DIAGNOSTIC_SHA:-}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

safe_value() {
  local value="${1:-}"
  if [[ -z "$value" ]]; then
    printf 'unset'
  else
    printf '%s' "$value"
  fi
}

[[ "$(id -u)" -eq 0 ]] || fail "diagnostic must run as root"
[[ "$(hostname -f)" == "$EXPECTED_HOST" ]] || fail "unexpected hostname"
[[ "$DIAGNOSTIC_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "NAILS_DIAGNOSTIC_SHA must be an exact commit SHA"
[[ -d "$REPO/.git" ]] || fail "repository checkout not found"

cd "$REPO"

git cat-file -e "${DIAGNOSTIC_SHA}^{commit}"
git cat-file -e "${DIAGNOSTIC_SHA}:ops/diagnostics/gateway-nails-preflight.sh"

HEAD_CURRENT="$(git rev-parse HEAD)"
BRANCH_CURRENT="$(git branch --show-current)"
TREE_CLEAN="false"
[[ -z "$(git status --porcelain)" ]] && TREE_CLEAN="true"

ACTIVE_STATE="$(systemctl show "$GATEWAY" -p ActiveState --value 2>/dev/null || true)"
SUB_STATE="$(systemctl show "$GATEWAY" -p SubState --value 2>/dev/null || true)"
LOAD_STATE="$(systemctl show "$GATEWAY" -p LoadState --value 2>/dev/null || true)"
UNIT_FILE_STATE="$(systemctl show "$GATEWAY" -p UnitFileState --value 2>/dev/null || true)"
RESULT="$(systemctl show "$GATEWAY" -p Result --value 2>/dev/null || true)"
MAIN_PID="$(systemctl show "$GATEWAY" -p MainPID --value 2>/dev/null || true)"
EXEC_MAIN_CODE="$(systemctl show "$GATEWAY" -p ExecMainCode --value 2>/dev/null || true)"
EXEC_MAIN_STATUS="$(systemctl show "$GATEWAY" -p ExecMainStatus --value 2>/dev/null || true)"
N_RESTARTS="$(systemctl show "$GATEWAY" -p NRestarts --value 2>/dev/null || true)"
RESTART_POLICY="$(systemctl show "$GATEWAY" -p Restart --value 2>/dev/null || true)"
FRAGMENT_PATH="$(systemctl show "$GATEWAY" -p FragmentPath --value 2>/dev/null || true)"
DROPIN_PATHS="$(systemctl show "$GATEWAY" -p DropInPaths --value 2>/dev/null || true)"
ACTIVE_ENTER="$(systemctl show "$GATEWAY" -p ActiveEnterTimestamp --value 2>/dev/null || true)"
ACTIVE_EXIT="$(systemctl show "$GATEWAY" -p ActiveExitTimestamp --value 2>/dev/null || true)"
INACTIVE_ENTER="$(systemctl show "$GATEWAY" -p InactiveEnterTimestamp --value 2>/dev/null || true)"
STATE_CHANGE="$(systemctl show "$GATEWAY" -p StateChangeTimestamp --value 2>/dev/null || true)"

FRAGMENT_STAT="missing"
if [[ -n "$FRAGMENT_PATH" && -f "$FRAGMENT_PATH" ]]; then
  FRAGMENT_STAT="$(stat -c '%a %U:%G %s bytes' "$FRAGMENT_PATH")"
fi

PROFILE_STATE="missing"
[[ -d "$PROFILE" ]] && PROFILE_STATE="$(stat -c '%a %U:%G' "$PROFILE")"
PROFILE_ENV_STATE="missing"
[[ -f "$PROFILE_ENV" ]] && PROFILE_ENV_STATE="$(stat -c '%a %U:%G %s bytes' "$PROFILE_ENV")"

HEALTH="failed"
READY="failed"
curl -fsS --max-time 5 "${API_BASE}/health" >/dev/null 2>&1 && HEALTH="ok"
curl -fsS --max-time 5 "${API_BASE}/ready" >/dev/null 2>&1 && READY="ok"

ALLOWLIST_MATCHES="$(
  {
    grep -RIlZF \
      --exclude-dir=backups \
      --exclude-dir=plugins \
      --exclude-dir=skills \
      -- 'clarify,image_gen,nails_onboarding,skills,tts,vision' \
      "$PROFILE" 2>/dev/null || true
  } | wc -l | tr -d ' '
)"

printf 'NAILS_GATEWAY_DIAGNOSTIC\n'
printf 'runbook=%s\n' "$RUNBOOK_ID"
printf 'diagnostic_sha=%s\n' "$DIAGNOSTIC_SHA"
printf 'timestamp_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'hostname=%s\n' "$(hostname -f)"
printf 'repo_head=%s\n' "$HEAD_CURRENT"
printf 'repo_branch=%s\n' "$(safe_value "$BRANCH_CURRENT")"
printf 'repo_tree_clean=%s\n' "$TREE_CLEAN"
printf 'backend_health=%s\n' "$HEALTH"
printf 'backend_ready=%s\n' "$READY"
printf 'gateway_load_state=%s\n' "$(safe_value "$LOAD_STATE")"
printf 'gateway_active_state=%s\n' "$(safe_value "$ACTIVE_STATE")"
printf 'gateway_sub_state=%s\n' "$(safe_value "$SUB_STATE")"
printf 'gateway_unit_file_state=%s\n' "$(safe_value "$UNIT_FILE_STATE")"
printf 'gateway_result=%s\n' "$(safe_value "$RESULT")"
printf 'gateway_main_pid=%s\n' "$(safe_value "$MAIN_PID")"
printf 'gateway_exec_main_code=%s\n' "$(safe_value "$EXEC_MAIN_CODE")"
printf 'gateway_exec_main_status=%s\n' "$(safe_value "$EXEC_MAIN_STATUS")"
printf 'gateway_restart_policy=%s\n' "$(safe_value "$RESTART_POLICY")"
printf 'gateway_restart_count=%s\n' "$(safe_value "$N_RESTARTS")"
printf 'gateway_active_enter=%s\n' "$(safe_value "$ACTIVE_ENTER")"
printf 'gateway_active_exit=%s\n' "$(safe_value "$ACTIVE_EXIT")"
printf 'gateway_inactive_enter=%s\n' "$(safe_value "$INACTIVE_ENTER")"
printf 'gateway_state_change=%s\n' "$(safe_value "$STATE_CHANGE")"
printf 'gateway_fragment_path=%s\n' "$(safe_value "$FRAGMENT_PATH")"
printf 'gateway_fragment_stat=%s\n' "$FRAGMENT_STAT"
printf 'gateway_dropins=%s\n' "$(safe_value "$DROPIN_PATHS")"
printf 'profile_stat=%s\n' "$PROFILE_STATE"
printf 'profile_env_stat=%s\n' "$PROFILE_ENV_STATE"
printf 'old_allowlist_match_count=%s\n' "$ALLOWLIST_MATCHES"
printf 'changes_executed=false\n'

printf '\nSANITIZED_GATEWAY_LOG_TAIL_BEGIN\n'
{ journalctl -u "$GATEWAY" -n 120 --no-pager -o short-iso 2>/dev/null || true; } | python3 /dev/fd/3 3<<'PY'
import re
import sys

patterns = [
    (re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"), "<telegram-token>"),
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)(\s*[=:]\s*)(\S+)"), r"\1\2<redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "<long-hex-redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}\b"), "<uuid-redacted>"),
    (re.compile(r"(?i)\b(telegram|chat|user)[_-]?(id)?(\s*[=:]\s*)\d{5,}\b"), r"\1_id\3<number-redacted>"),
]

for raw in sys.stdin:
    line = raw.rstrip("\n")
    for pattern, replacement in patterns:
        line = pattern.sub(replacement, line)
    print(line[:1200])
PY
printf 'SANITIZED_GATEWAY_LOG_TAIL_END\n'
