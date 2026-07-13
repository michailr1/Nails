#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

RUNBOOK_ID="NAILS-HERMES-RUNTIME-DISCOVERY"
EXPECTED_HOST="de.funti.cc"
REPO="/opt/nails/repo"
PROFILE="/root/.hermes/profiles/nails"
DIAGNOSTIC_SHA="${NAILS_DIAGNOSTIC_SHA:-}"
MATCH_RE='hermes|nails|gateway'

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

sanitize_stream() {
  python3 /dev/fd/3 3<<'PY'
import re
import sys

patterns = [
    (re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"), "<telegram-token>"),
    (re.compile(r"\b(?:sk|xsmtpsib)-[A-Za-z0-9_-]{10,}\b", re.I), "<secret-token>"),
    (
        re.compile(
            r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)"
            r"(\s*[=:]\s*)([^\s;]+)"
        ),
        r"\1\2<redacted>",
    ),
    (re.compile(r"(?i)(Environment\s*=\s*).+"), r"\1<redacted>"),
    (re.compile(r"([?&][^=\s]+)=([^&\s]+)"), r"\1=<redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "<long-hex-redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}\b"), "<uuid-redacted>"),
    (
        re.compile(r"(?i)\b(telegram|chat|user)[_-]?(id)?(\s*[=:]\s*)\d{5,}\b"),
        r"\1_id\3<number-redacted>",
    ),
    (re.compile(r"\b\d{8,}\b"), "<long-number-redacted>"),
]

for raw in sys.stdin:
    line = raw.rstrip("\n")
    for pattern, replacement in patterns:
        line = pattern.sub(replacement, line)
    print(line[:1600])
PY
}

section() {
  printf '\n===== %s =====\n' "$1"
}

[[ "$(id -u)" -eq 0 ]] || fail "diagnostic must run as root"
[[ "$(hostname -f)" == "$EXPECTED_HOST" ]] || fail "unexpected hostname"
[[ "$DIAGNOSTIC_SHA" =~ ^[0-9a-f]{40}$ ]] \
  || fail "NAILS_DIAGNOSTIC_SHA must be an exact commit SHA"
[[ -d "$REPO/.git" ]] || fail "repository checkout not found"

cd "$REPO"
git cat-file -e "${DIAGNOSTIC_SHA}^{commit}"
git cat-file -e "${DIAGNOSTIC_SHA}:ops/diagnostics/hermes-runtime-discovery.sh"

printf 'NAILS_HERMES_RUNTIME_DISCOVERY\n'
printf 'runbook=%s\n' "$RUNBOOK_ID"
printf 'diagnostic_sha=%s\n' "$DIAGNOSTIC_SHA"
printf 'timestamp_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'hostname=%s\n' "$(hostname -f)"
printf 'repo_head=%s\n' "$(git rev-parse HEAD)"
printf 'repo_branch=%s\n' "$(git branch --show-current)"
printf 'repo_tree_clean=%s\n' "$([[ -z "$(git status --porcelain)" ]] && printf true || printf false)"
printf 'changes_executed=false\n'

section "SYSTEM_SYSTEMD_LOADED_SERVICES"
{
  systemctl list-units --type=service --all --no-legend --no-pager 2>&1 \
    | grep -Ei "$MATCH_RE" || true
} | sanitize_stream

section "SYSTEM_SYSTEMD_UNIT_FILES"
{
  systemctl list-unit-files --type=service --no-legend --no-pager 2>&1 \
    | grep -Ei "$MATCH_RE" || true
} | sanitize_stream

section "SYSTEM_SYSTEMD_TIMERS"
{
  systemctl list-timers --all --no-legend --no-pager 2>&1 \
    | grep -Ei "$MATCH_RE" || true
} | sanitize_stream

section "ROOT_USER_SYSTEMD_LOADED_SERVICES"
{
  XDG_RUNTIME_DIR=/run/user/0 systemctl --user list-units \
    --type=service --all --no-legend --no-pager 2>&1 \
    | grep -Ei "$MATCH_RE|Failed to connect|No such file|not available" || true
} | sanitize_stream

section "ROOT_USER_SYSTEMD_UNIT_FILES"
{
  XDG_RUNTIME_DIR=/run/user/0 systemctl --user list-unit-files \
    --type=service --no-legend --no-pager 2>&1 \
    | grep -Ei "$MATCH_RE|Failed to connect|No such file|not available" || true
} | sanitize_stream

section "CANDIDATE_UNIT_FILES_AND_CONTENT"
UNIT_DIRS=(
  /etc/systemd/system
  /run/systemd/system
  /usr/local/lib/systemd/system
  /usr/lib/systemd/system
  /lib/systemd/system
  /root/.config/systemd/user
  /etc/systemd/user
  /usr/local/lib/systemd/user
  /usr/lib/systemd/user
  /lib/systemd/user
)

for directory in "${UNIT_DIRS[@]}"; do
  [[ -d "$directory" ]] || continue
  while IFS= read -r candidate; do
    printf -- '--- candidate=%s\n' "$candidate"
    stat -c 'stat=%a %U:%G %s bytes %y' "$candidate" 2>/dev/null || true
    if [[ -L "$candidate" ]]; then
      printf 'symlink_target=%s\n' "$(readlink "$candidate" 2>/dev/null || true)"
    fi
    if [[ -f "$candidate" ]]; then
      sed -n '1,220p' "$candidate" 2>/dev/null || true
    fi
  done < <(
    find "$directory" -maxdepth 4 \( -type f -o -type l \) \
      -iregex '.*\(hermes\|nails\|gateway\).*' -print 2>/dev/null \
      | LC_ALL=C sort
  )
done | sanitize_stream

section "MATCHING_PROCESSES"
{
  ps -eo pid=,ppid=,user=,lstart=,cmd= --ww 2>&1 \
    | grep -Ei "$MATCH_RE|telegram" \
    | grep -Ev 'grep -E|hermes-runtime-discovery' || true
} | sanitize_stream

section "MATCHING_DOCKER_CONTAINERS"
{
  docker ps -a --no-trunc \
    --format 'id={{.ID}} name={{.Names}} image={{.Image}} status={{.Status}} command={{.Command}}' \
    2>&1 | grep -Ei "$MATCH_RE|telegram" || true
} | sanitize_stream

section "MATCHING_LISTENING_SOCKETS"
{
  ss -ltnpH 2>&1 | grep -Ei "$MATCH_RE|python|node|hermes" || true
} | sanitize_stream

section "TMUX_SESSIONS"
{ tmux list-sessions 2>&1 || true; } | sanitize_stream

section "SCREEN_SESSIONS"
{ screen -ls 2>&1 || true; } | sanitize_stream

section "ROOT_CRONTAB_MATCHES"
{
  crontab -l 2>&1 | grep -Ei "$MATCH_RE|telegram" || true
} | sanitize_stream

section "SYSTEM_CRON_MATCHES"
{
  for path in /etc/crontab /etc/cron.d /etc/cron.hourly /etc/cron.daily /etc/cron.weekly /etc/cron.monthly; do
    [[ -e "$path" ]] || continue
    if [[ -f "$path" ]]; then
      grep -HinE "$MATCH_RE|telegram" "$path" 2>/dev/null || true
    elif [[ -d "$path" ]]; then
      grep -RHinE "$MATCH_RE|telegram" "$path" 2>/dev/null || true
    fi
  done
} | sanitize_stream

section "PROFILE_RUNTIME_ARTIFACTS"
if [[ -d "$PROFILE" ]]; then
  find "$PROFILE" -maxdepth 5 \( -type f -o -type l -o -type d \) \
    -iregex '.*\(pid\|log\|service\|unit\|gateway\|launch\|runner\|runtime\|socket\).*' \
    -printf '%y %m %u:%g %s bytes %TY-%Tm-%TdT%TH:%TM:%TS %p -> %l\n' \
    2>/dev/null | LC_ALL=C sort | head -n 300 | sanitize_stream
else
  printf 'profile_missing=true\n'
fi

section "RECENT_GLOBAL_JOURNAL_MATCHES"
{
  journalctl --since '30 days ago' --no-pager -o short-iso 2>/dev/null \
    | grep -Ei "$MATCH_RE|telegram" \
    | tail -n 240 || true
} | sanitize_stream

section "DISCOVERY_SUMMARY_COUNTS"
SYSTEM_UNIT_MATCHES="$(
  systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null \
    | grep -Eic "$MATCH_RE" || true
)"
PROCESS_MATCHES="$(
  ps -eo cmd= --ww 2>/dev/null \
    | grep -Ei "$MATCH_RE|telegram" \
    | grep -Ev 'grep -E|hermes-runtime-discovery' \
    | wc -l | tr -d ' '
)"
DOCKER_MATCHES="$(
  docker ps -a --format '{{.Names}} {{.Image}} {{.Command}}' 2>/dev/null \
    | grep -Eic "$MATCH_RE|telegram" || true
)"
printf 'system_unit_file_matches=%s\n' "$SYSTEM_UNIT_MATCHES"
printf 'process_matches=%s\n' "$PROCESS_MATCHES"
printf 'docker_matches=%s\n' "$DOCKER_MATCHES"
printf 'changes_executed=false\n'
printf 'NAILS_HERMES_RUNTIME_DISCOVERY_END\n'
