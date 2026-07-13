#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

RUNBOOK_ID="NAILS-002E4"
EXPECTED_HOST="de.funti.cc"
EXPECTED_BEFORE="5565a524b75a04fe5d8bc2c3e758d2994e9d9c12"
EXPECTED_FEATURE_ANCESTOR="77b6ca69286d7f2c203a85c04f4224f783038fdf"
RELEASE_SHA="${NAILS_RELEASE_SHA:-}"

REPO="/opt/nails/repo"
BACKEND_ENV="/opt/nails/.env"
PROFILE="/root/.hermes/profiles/nails"
PROFILE_ENV="${PROFILE}/.env"
GATEWAY="hermes-gateway-nails.service"
API_BASE="http://127.0.0.1:8210"

PLUGIN_SOURCE="${REPO}/hermes/plugins/nails_scheduling"
PLUGIN_TARGET="${PROFILE}/plugins/nails_scheduling"
SKILL_SOURCE="${REPO}/hermes/skills/nails-scheduling/SKILL.md"
SKILL_TARGET="${PROFILE}/skills/nails-scheduling/SKILL.md"

OLD_ALLOWLIST="clarify,image_gen,nails_onboarding,skills,tts,vision"
NEW_ALLOWLIST="clarify,image_gen,nails_onboarding,nails_scheduling,skills,tts,vision"

RELEASE_FILES=(
  "__init__.py"
  "operations.py"
  "plugin.yaml"
  "presenters.py"
  "schemas.py"
  "tools.py"
  "transport.py"
  "validation.py"
)

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${PROFILE}/backups/nails-002e4-${STAMP}"
LOG_SINCE="$(date '+%Y-%m-%d %H:%M:%S')"

HEAD_BEFORE=""
ALLOWLIST_FILE=""
PLUGIN_EXISTED="false"
SKILL_EXISTED="false"
REPO_UPDATED="false"
RUNTIME_TOUCHED="false"
ROLLBACK_PERFORMED="false"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  return 1
}

require_release_sha() {
  [[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]] \
    || fail "NAILS_RELEASE_SHA must be the exact approved 40-character commit SHA"
}

read_env_value() {
  local file="$1"
  local key="$2"

  FILE_PATH="$file" ENV_KEY="$key" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["FILE_PATH"])
wanted = os.environ["ENV_KEY"]

for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].strip()
    key, separator, value = line.partition("=")
    if separator and key.strip() == wanted:
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        print(value, end="")
        raise SystemExit(0)

raise SystemExit(1)
PY
}

verify_keys_match() {
  local backend_key profile_key

  backend_key="$(read_env_value "$BACKEND_ENV" "INTERNAL_API_KEY")"
  profile_key="$(read_env_value "$PROFILE_ENV" "NAILS_INTERNAL_API_KEY")"

  [[ ${#backend_key} -ge 32 ]] || fail "backend INTERNAL_API_KEY is missing or too short"
  [[ ${#profile_key} -ge 32 ]] || fail "profile NAILS_INTERNAL_API_KEY is missing or too short"

  BACKEND_KEY="$backend_key" PROFILE_KEY="$profile_key" python3 - <<'PY'
import hmac
import os

if not hmac.compare_digest(os.environ["BACKEND_KEY"], os.environ["PROFILE_KEY"]):
    raise SystemExit("gateway/backend keys do not match")

print("KEYS_MATCH=true")
PY

  unset backend_key profile_key
}

rollback() {
  local original_rc="${1:-1}"

  set +e
  trap - ERR

  if [[ "$RUNTIME_TOUCHED" == "true" ]]; then
    systemctl stop "$GATEWAY" >/dev/null 2>&1 || true

    rm -rf "$PLUGIN_TARGET"
    if [[ "$PLUGIN_EXISTED" == "true" ]]; then
      cp -a "${BACKUP_DIR}/plugin.before" "$PLUGIN_TARGET"
    fi

    rm -f "$SKILL_TARGET"
    if [[ "$SKILL_EXISTED" == "true" ]]; then
      install -d -o root -g root -m 700 "$(dirname "$SKILL_TARGET")"
      cp -a "${BACKUP_DIR}/skill.before" "$SKILL_TARGET"
    fi

    if [[ -n "$ALLOWLIST_FILE" && -f "${BACKUP_DIR}/allowlist.before" ]]; then
      cp -a "${BACKUP_DIR}/allowlist.before" "$ALLOWLIST_FILE"
    fi
  fi

  if [[ "$REPO_UPDATED" == "true" && -n "$HEAD_BEFORE" ]]; then
    git -C "$REPO" reset --hard "$HEAD_BEFORE" >/dev/null 2>&1 || true
  fi

  if [[ "$RUNTIME_TOUCHED" == "true" ]]; then
    systemctl start "$GATEWAY" >/dev/null 2>&1 || true
  fi

  ROLLBACK_PERFORMED="true"

  printf '\nROLLBACK_PERFORMED=true\n'
  printf 'ROLLBACK_TARGET_HEAD=%s\n' "${HEAD_BEFORE:-unknown}"
  printf 'ROLLBACK_GATEWAY_STATE=%s\n' "$(systemctl is-active "$GATEWAY" 2>/dev/null || true)"

  return "$original_rc"
}

on_error() {
  local rc="$?"
  local line="$1"

  printf '\nDEPLOYMENT_FAILED=true\n'
  printf 'runbook=%s\n' "$RUNBOOK_ID"
  printf 'failed_line=%s\n' "$line"
  printf 'head_current=%s\n' "$(git -C "$REPO" rev-parse HEAD 2>/dev/null || true)"
  printf 'gateway_state=%s\n' "$(systemctl is-active "$GATEWAY" 2>/dev/null || true)"
  printf 'backup_dir=%s\n' "${BACKUP_DIR:-not-created}"

  rollback "$rc"
  exit "$rc"
}

trap 'on_error "$LINENO"' ERR

printf '== %s: 1. Preflight ==\n' "$RUNBOOK_ID"

require_release_sha
[[ "$(id -u)" -eq 0 ]] || fail "runbook must be executed as root"
[[ "$(hostname -f)" == "$EXPECTED_HOST" ]] || fail "unexpected hostname"
[[ -d "$REPO/.git" ]] || fail "repository checkout not found"
[[ -f "$BACKEND_ENV" ]] || fail "backend environment file not found"
[[ -d "$PROFILE" ]] || fail "Hermes nails profile not found"
[[ -f "$PROFILE_ENV" ]] || fail "Hermes profile environment file not found"

[[ "$(stat -c '%a %U:%G' "$BACKEND_ENV")" == "600 root:root" ]] \
  || fail "unexpected backend env ownership or mode"
[[ "$(stat -c '%a %U:%G' "$PROFILE_ENV")" == "600 root:root" ]] \
  || fail "unexpected profile env ownership or mode"

cd "$REPO"

[[ "$(git branch --show-current)" == "main" ]] || fail "production checkout is not on main"
[[ -z "$(git status --porcelain)" ]] || fail "production working tree is not clean"

HEAD_BEFORE="$(git rev-parse HEAD)"
[[ "$HEAD_BEFORE" == "$EXPECTED_BEFORE" ]] || fail "unexpected production HEAD before deployment"

# The launcher fetches before reading this script from the approved commit. Fetch again to
# make the script independently verify the remote state immediately before deployment.
git fetch --quiet origin main

[[ "$(git rev-parse origin/main)" == "$RELEASE_SHA" ]] \
  || fail "origin/main does not equal the approved release SHA"
git cat-file -e "${RELEASE_SHA}^{commit}"
git merge-base --is-ancestor "$EXPECTED_BEFORE" "$RELEASE_SHA" \
  || fail "approved release is not a descendant of production HEAD"
git merge-base --is-ancestor "$EXPECTED_FEATURE_ANCESTOR" "$RELEASE_SHA" \
  || fail "approved release does not contain the reviewed scheduling implementation"
git cat-file -e "${RELEASE_SHA}:ops/deploy/nails-002e4.sh"

curl -fsS "${API_BASE}/health" >/dev/null
curl -fsS "${API_BASE}/ready" >/dev/null
systemctl is-active --quiet "$GATEWAY" || fail "gateway is not active before deployment"

GATEWAY_PID_BEFORE="$(systemctl show "$GATEWAY" -p MainPID --value)"
[[ "$GATEWAY_PID_BEFORE" =~ ^[1-9][0-9]*$ ]] || fail "gateway MainPID is invalid before deployment"

API_CONTAINER_BEFORE="$(docker compose --env-file "$BACKEND_ENV" ps -q nails-api)"
[[ -n "$API_CONTAINER_BEFORE" ]] || fail "nails-api container was not found"
API_ID_BEFORE="$(docker inspect -f '{{.Id}}' "$API_CONTAINER_BEFORE")"
API_STARTED_BEFORE="$(docker inspect -f '{{.State.StartedAt}}' "$API_CONTAINER_BEFORE")"

verify_keys_match

mapfile -d '' -t ALLOWLIST_FILES < <(
  grep -RIlZF \
    --exclude-dir=backups \
    --exclude-dir=plugins \
    --exclude-dir=skills \
    -- "$OLD_ALLOWLIST" "$PROFILE" 2>/dev/null || true
)

[[ "${#ALLOWLIST_FILES[@]}" -eq 1 ]] \
  || fail "expected exactly one profile file containing the old allowlist"

ALLOWLIST_FILE="${ALLOWLIST_FILES[0]}"
[[ -f "$ALLOWLIST_FILE" ]] || fail "allowlist file is not a regular file"
[[ ! -L "$ALLOWLIST_FILE" ]] || fail "allowlist file must not be a symlink"

case "$(readlink -f "$ALLOWLIST_FILE")" in
  "${PROFILE}"/*) ;;
  *) fail "allowlist file resolved outside the nails profile" ;;
esac

ALLOWLIST_FILE="$ALLOWLIST_FILE" \
OLD_ALLOWLIST="$OLD_ALLOWLIST" \
NEW_ALLOWLIST="$NEW_ALLOWLIST" \
python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ALLOWLIST_FILE"])
old = os.environ["OLD_ALLOWLIST"]
new = os.environ["NEW_ALLOWLIST"]
text = path.read_text(encoding="utf-8")

assert text.count(old) == 1, "old allowlist must occur exactly once"
assert new not in text, "new allowlist is already present"
print("ALLOWLIST_PRECHECK=true")
PY

printf '== %s: 2. Backup ==\n' "$RUNBOOK_ID"

install -d -o root -g root -m 700 "$BACKUP_DIR"
cp -a "$ALLOWLIST_FILE" "${BACKUP_DIR}/allowlist.before"
printf '%s\n' "$ALLOWLIST_FILE" >"${BACKUP_DIR}/allowlist.path"
printf '%s\n' "$HEAD_BEFORE" >"${BACKUP_DIR}/head.before"
printf '%s\n' "$RELEASE_SHA" >"${BACKUP_DIR}/head.approved"

if [[ -e "$PLUGIN_TARGET" ]]; then
  cp -a "$PLUGIN_TARGET" "${BACKUP_DIR}/plugin.before"
  PLUGIN_EXISTED="true"
else
  : >"${BACKUP_DIR}/plugin.absent"
fi

if [[ -e "$SKILL_TARGET" ]]; then
  cp -a "$SKILL_TARGET" "${BACKUP_DIR}/skill.before"
  SKILL_EXISTED="true"
else
  : >"${BACKUP_DIR}/skill.absent"
fi

[[ "$(stat -c '%a %U:%G' "$BACKUP_DIR")" == "700 root:root" ]] \
  || fail "backup directory ownership or mode is invalid"

printf '== %s: 3. Exact repository update ==\n' "$RUNBOOK_ID"

git merge --ff-only "$RELEASE_SHA"
REPO_UPDATED="true"

[[ "$(git rev-parse HEAD)" == "$RELEASE_SHA" ]] || fail "unexpected HEAD after fast-forward"
[[ -z "$(git status --porcelain)" ]] || fail "working tree is not clean after fast-forward"

printf '== %s: 4. Static release validation ==\n' "$RUNBOOK_ID"

[[ -d "$PLUGIN_SOURCE" ]] || fail "scheduling plugin source directory is missing"
[[ -f "$SKILL_SOURCE" ]] || fail "scheduling skill source is missing"

for file in "${RELEASE_FILES[@]}"; do
  [[ -f "${PLUGIN_SOURCE}/${file}" ]] || fail "missing release file: ${file}"
  [[ ! -L "${PLUGIN_SOURCE}/${file}" ]] || fail "release file is a symlink: ${file}"
done

REPO="$REPO" python3 - <<'PY'
import ast
import os
from pathlib import Path

repo = Path(os.environ["REPO"])
plugin = repo / "hermes/plugins/nails_scheduling"
skill = repo / "hermes/skills/nails-scheduling/SKILL.md"

module = ast.parse((plugin / "schemas.py").read_text(encoding="utf-8"))
schema = None
for node in module.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "NAILS_SCHEDULING"
        for target in node.targets
    ):
        schema = ast.literal_eval(node.value)
        break

assert isinstance(schema, dict)
assert schema["name"] == "nails_scheduling"
parameters = schema["parameters"]
assert parameters["type"] == "object"
assert parameters["additionalProperties"] is False
assert parameters["required"] == ["action"]

properties = parameters["properties"]
assert set(properties) == {
    "action",
    "day",
    "service_name",
    "client_public_name",
    "phone",
    "start_time",
    "confirmed",
}
assert set(properties["action"]["enum"]) == {
    "list_services",
    "day_view",
    "free_slots",
    "find_client",
    "create_client",
    "create_booking",
}

for forbidden in {
    "telegram_user_id",
    "owner_user_id",
    "user_id",
    "api_key",
    "headers",
    "url",
    "endpoint",
    "idempotency_key",
    "service_id",
    "client_id",
    "booking_id",
    "price",
    "currency",
    "duration",
    "buffers",
}:
    assert forbidden not in properties

manifest = (plugin / "plugin.yaml").read_text(encoding="utf-8")
assert "name: nails-scheduling" in manifest
assert "version: 0.1.0" in manifest
assert "name: NAILS_INTERNAL_API_KEY" in manifest
assert "secret: true" in manifest
assert "  - nails_scheduling" in manifest

transport = (plugin / "transport.py").read_text(encoding="utf-8")
assert '_API_BASE_URL = "http://127.0.0.1:8210"' in transport
assert "_RETRYABLE_STATUS_CODES = {502, 503, 504}" in transport
assert '"X-Nails-Internal-Key": api_key' in transport
assert '"X-Telegram-User-ID": telegram_user_id' in transport
assert "follow_redirects=False" in transport

tools = (plugin / "tools.py").read_text(encoding="utf-8")
assert "HERMES_SESSION_PLATFORM" in tools
assert "HERMES_SESSION_USER_ID" in tools
assert '_API_KEY_ENV = "NAILS_INTERNAL_API_KEY"' in tools
assert 'platform != "telegram"' in tools

operations = (plugin / "operations.py").read_text(encoding="utf-8")
assert "nails-scheduling-v1-" in operations
assert 'path="/api/v1/scheduling/slots"' in operations
assert 'path="/api/v1/scheduling/bookings"' in operations

skill_text = skill.read_text(encoding="utf-8")
assert "Думаю… (nails_scheduling)" in skill_text
assert "weekday_iso" in skill_text
assert "create_client" in skill_text
assert "create_booking" in skill_text

print("STATIC_RELEASE_VALIDATION=true")
PY

printf '== %s: 5. Stop only the Nails gateway ==\n' "$RUNBOOK_ID"

RUNTIME_TOUCHED="true"
systemctl stop "$GATEWAY" || true

for _ in $(seq 1 30); do
  CURRENT_PID="$(systemctl show "$GATEWAY" -p MainPID --value 2>/dev/null || true)"
  [[ "$CURRENT_PID" == "0" || -z "$CURRENT_PID" ]] && break
  sleep 1
done

GATEWAY_STOP_PID="$(systemctl show "$GATEWAY" -p MainPID --value 2>/dev/null || true)"
GATEWAY_STOP_STATE="$(systemctl is-active "$GATEWAY" 2>/dev/null || true)"

[[ "$GATEWAY_STOP_PID" == "0" || -z "$GATEWAY_STOP_PID" ]] || fail "gateway did not stop"
[[ "$GATEWAY_STOP_STATE" == "inactive" || "$GATEWAY_STOP_STATE" == "failed" ]] \
  || fail "unexpected gateway state after stop"

printf '== %s: 6. Install exact runtime files ==\n' "$RUNBOOK_ID"

rm -rf "$PLUGIN_TARGET"
install -d -o root -g root -m 700 "$PLUGIN_TARGET"

for file in "${RELEASE_FILES[@]}"; do
  install -o root -g root -m 600 "${PLUGIN_SOURCE}/${file}" "${PLUGIN_TARGET}/${file}"
done

install -d -o root -g root -m 700 "$(dirname "$SKILL_TARGET")"
install -o root -g root -m 600 "$SKILL_SOURCE" "$SKILL_TARGET"

ALLOWLIST_FILE="$ALLOWLIST_FILE" \
OLD_ALLOWLIST="$OLD_ALLOWLIST" \
NEW_ALLOWLIST="$NEW_ALLOWLIST" \
python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ALLOWLIST_FILE"])
old = os.environ["OLD_ALLOWLIST"]
new = os.environ["NEW_ALLOWLIST"]
text = path.read_text(encoding="utf-8")

assert text.count(old) == 1
assert new not in text
path.write_text(text.replace(old, new), encoding="utf-8")
PY

printf '== %s: 7. Verify runtime before restart ==\n' "$RUNBOOK_ID"

EXPECTED_FILES="$(printf '%s\n' "${RELEASE_FILES[@]}" | LC_ALL=C sort)"
ACTUAL_FILES="$(
  find "$PLUGIN_TARGET" -mindepth 1 -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort
)"

[[ "$ACTUAL_FILES" == "$EXPECTED_FILES" ]] || fail "runtime plugin contains unexpected or missing files"
[[ -z "$(find "$PLUGIN_TARGET" -mindepth 1 -maxdepth 1 ! -type f -print -quit)" ]] \
  || fail "runtime plugin contains a non-file entry"
[[ "$(stat -c '%a %U:%G' "$PLUGIN_TARGET")" == "700 root:root" ]] \
  || fail "runtime plugin directory ownership or mode is invalid"

for file in "${RELEASE_FILES[@]}"; do
  [[ "$(stat -c '%a %U:%G' "${PLUGIN_TARGET}/${file}")" == "600 root:root" ]] \
    || fail "invalid ownership or mode for runtime file: ${file}"
  cmp -s "${PLUGIN_SOURCE}/${file}" "${PLUGIN_TARGET}/${file}" \
    || fail "source/target mismatch for runtime file: ${file}"
done

[[ "$(stat -c '%a %U:%G' "$SKILL_TARGET")" == "600 root:root" ]] \
  || fail "runtime skill ownership or mode is invalid"
cmp -s "$SKILL_SOURCE" "$SKILL_TARGET" || fail "scheduling skill source/target mismatch"

ALLOWLIST_FILE="$ALLOWLIST_FILE" \
OLD_ALLOWLIST="$OLD_ALLOWLIST" \
NEW_ALLOWLIST="$NEW_ALLOWLIST" \
python3 - <<'PY'
import os
from pathlib import Path

text = Path(os.environ["ALLOWLIST_FILE"]).read_text(encoding="utf-8")
old = os.environ["OLD_ALLOWLIST"]
new = os.environ["NEW_ALLOWLIST"]

assert old not in text
assert text.count(new) == 1
print("ALLOWLIST_UPDATED=true")
PY

printf '== %s: 8. Restart only the Nails gateway ==\n' "$RUNBOOK_ID"

systemctl start "$GATEWAY"

for _ in $(seq 1 60); do
  systemctl is-active --quiet "$GATEWAY" && break
  sleep 1
done

systemctl is-active --quiet "$GATEWAY" || fail "gateway did not become active"

GATEWAY_PID_AFTER="$(systemctl show "$GATEWAY" -p MainPID --value)"
[[ "$GATEWAY_PID_AFTER" =~ ^[1-9][0-9]*$ ]] || fail "gateway MainPID is invalid after deployment"
[[ "$GATEWAY_PID_AFTER" != "$GATEWAY_PID_BEFORE" ]] || fail "gateway PID did not change"

sleep 3
GATEWAY_LOG="${BACKUP_DIR}/gateway-after-deployment.log"
journalctl -u "$GATEWAY" --since "$LOG_SINCE" --no-pager >"$GATEWAY_LOG"
chmod 600 "$GATEWAY_LOG"
chown root:root "$GATEWAY_LOG"

if grep -Eiq \
  'traceback|importerror|modulenotfounderror|syntaxerror|manifest[^[:alnum:]]+error|plugin[^[:alnum:]]+error|missing[^[:alnum:]]+NAILS_INTERNAL_API_KEY|polling conflict|unauthorized' \
  "$GATEWAY_LOG"
then
  fail "gateway log contains a plugin/import/configuration error"
fi

PLUGIN_LOG_MENTIONS="$(grep -Eic 'nails[-_]scheduling' "$GATEWAY_LOG" || true)"
verify_keys_match

printf '== %s: 9. Verify backend unchanged ==\n' "$RUNBOOK_ID"

API_CONTAINER_AFTER="$(docker compose --env-file "$BACKEND_ENV" ps -q nails-api)"
[[ -n "$API_CONTAINER_AFTER" ]] || fail "nails-api container disappeared"
API_ID_AFTER="$(docker inspect -f '{{.Id}}' "$API_CONTAINER_AFTER")"
API_STARTED_AFTER="$(docker inspect -f '{{.State.StartedAt}}' "$API_CONTAINER_AFTER")"

[[ "$API_ID_AFTER" == "$API_ID_BEFORE" ]] || fail "nails-api container changed"
[[ "$API_STARTED_AFTER" == "$API_STARTED_BEFORE" ]] || fail "nails-api StartedAt changed"

curl -fsS "${API_BASE}/health" >/dev/null
curl -fsS "${API_BASE}/ready" >/dev/null
[[ "$(git rev-parse HEAD)" == "$RELEASE_SHA" ]] || fail "final repository HEAD changed unexpectedly"
[[ -z "$(git status --porcelain)" ]] || fail "final repository working tree is not clean"

trap - ERR

printf '\nNAILS_002E4_DEPLOYMENT_OK\n'
printf 'runbook=%s\n' "$RUNBOOK_ID"
printf 'hostname=%s\n' "$(hostname -f)"
printf 'head_before=%s\n' "$HEAD_BEFORE"
printf 'head_after=%s\n' "$(git rev-parse HEAD)"
printf 'git_tree_clean=true\n'
printf 'backup_dir=%s\n' "$BACKUP_DIR"
printf 'allowlist_file=%s\n' "$ALLOWLIST_FILE"
printf 'allowlist=%s\n' "$NEW_ALLOWLIST"
printf 'plugin_source_target_match=true\n'
printf 'skill_source_target_match=true\n'
printf 'runtime_release_files_only=true\n'
printf 'plugin_dir_mode=%s\n' "$(stat -c '%a %U:%G' "$PLUGIN_TARGET")"
printf 'plugin_file_mode=600 root:root\n'
printf 'skill_file_mode=%s\n' "$(stat -c '%a %U:%G' "$SKILL_TARGET")"
printf 'gateway_pid_before=%s\n' "$GATEWAY_PID_BEFORE"
printf 'gateway_stop_state=%s\n' "$GATEWAY_STOP_STATE"
printf 'gateway_pid_after=%s\n' "$GATEWAY_PID_AFTER"
printf 'gateway_state=%s\n' "$(systemctl is-active "$GATEWAY")"
printf 'gateway_error_scan=clean\n'
printf 'gateway_nails_scheduling_log_mentions=%s\n' "$PLUGIN_LOG_MENTIONS"
printf 'backend_container_unchanged=true\n'
printf 'backend_started_at=%s\n' "$API_STARTED_AFTER"
printf 'backend_health=ok\n'
printf 'backend_ready=ok\n'
printf 'migration_executed=false\n'
printf 'database_write_executed=false\n'
printf 'backend_restart_executed=false\n'
printf 'rollback_performed=%s\n' "$ROLLBACK_PERFORMED"
