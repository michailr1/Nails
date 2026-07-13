#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

RUNBOOK_ID="NAILS-002E4-V3"
EXPECTED_HOST="de.funti.cc"
EXPECTED_BEFORE="5565a524b75a04fe5d8bc2c3e758d2994e9d9c12"
EXPECTED_FEATURE_ANCESTOR="77b6ca69286d7f2c203a85c04f4224f783038fdf"
EXPECTED_V2_ANCESTOR="b529b577fdaed5c8c1cfbcdbe24bce79a419004f"
RELEASE_SHA="${NAILS_RELEASE_SHA:-}"

REPO="/opt/nails/repo"
BACKEND_ENV="/opt/nails/.env"
PROFILE="/root/.hermes/profiles/nails"
PROFILE_ENV="${PROFILE}/.env"
PROFILE_CONFIG="${PROFILE}/config.yaml"
HERMES_ROOT="/usr/local/lib/hermes-agent"
HERMES_BIN="${HERMES_ROOT}/venv/bin/hermes"
HERMES_PYTHON="${HERMES_ROOT}/venv/bin/python"
GATEWAY="hermes-gateway-nails.service"
GATEWAY_FRAGMENT="/root/.config/systemd/user/hermes-gateway-nails.service"
USER_RUNTIME_DIR="/run/user/0"
API_BASE="http://127.0.0.1:8210"

PLUGIN_SOURCE="${REPO}/hermes/plugins/nails_scheduling"
PLUGIN_TARGET="${PROFILE}/plugins/nails_scheduling"
SKILL_SOURCE="${REPO}/hermes/skills/nails-scheduling/SKILL.md"
SKILL_TARGET="${PROFILE}/skills/nails-scheduling/SKILL.md"

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
BACKUP_DIR="${PROFILE}/backups/nails-002e4-v3-${STAMP}"
LOG_SINCE="$(date '+%Y-%m-%d %H:%M:%S')"

HEAD_BEFORE=""
MUTATION_STARTED="false"
PLUGIN_EXISTED="false"
SKILL_EXISTED="false"
ROLLBACK_PERFORMED="false"
GATEWAY_PID_BEFORE=""
GATEWAY_PID_AFTER=""
GATEWAY_STOP_STATE="not-stopped"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  return 1
}

user_systemctl() {
  XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" systemctl --user "$@"
}

user_journalctl() {
  XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" journalctl --user "$@"
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

verify_config_prestate() {
  PROFILE_CONFIG="$PROFILE_CONFIG" "$HERMES_PYTHON" - <<'PY'
import os
from pathlib import Path

import yaml

path = Path(os.environ["PROFILE_CONFIG"])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
assert isinstance(data, dict), type(data)

plugins = data.get("plugins")
assert isinstance(plugins, dict), plugins
assert plugins.get("enabled") == ["nails-onboarding"], plugins.get("enabled")
assert plugins.get("disabled") == [], plugins.get("disabled")
assert plugins.get("entries") == {
    "nails-onboarding": {"allow_tool_override": False},
}, plugins.get("entries")

assert data.get("toolsets") == ["hermes-cli"], data.get("toolsets")
assert "custom_toolsets" not in data
assert data.get("tools", {}).get("tool_search") == {
    "enabled": "auto",
    "threshold_pct": 10,
    "search_default_limit": 5,
    "max_search_limit": 20,
}, data.get("tools", {}).get("tool_search")
assert data.get("agent", {}).get("disabled_toolsets") == ["kanban"]
assert data.get("platform_toolsets", {}).get("telegram") == [
    "vision",
    "image_gen",
    "tts",
    "skills",
    "clarify",
    "nails_onboarding",
], data.get("platform_toolsets", {}).get("telegram")

print("CONFIG_PRESTATE_OK=true")
PY
}

verify_config_poststate() {
  PROFILE_CONFIG="$PROFILE_CONFIG" "$HERMES_PYTHON" - <<'PY'
import os
from pathlib import Path

import yaml

path = Path(os.environ["PROFILE_CONFIG"])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
assert isinstance(data, dict), type(data)

plugins = data.get("plugins")
assert isinstance(plugins, dict), plugins
assert plugins.get("enabled") == [
    "nails-onboarding",
    "nails-scheduling",
], plugins.get("enabled")
assert plugins.get("disabled") == [], plugins.get("disabled")
assert plugins.get("entries") == {
    "nails-onboarding": {"allow_tool_override": False},
}, plugins.get("entries")

assert data.get("toolsets") == ["hermes-cli"], data.get("toolsets")
assert "custom_toolsets" not in data
assert data.get("tools", {}).get("tool_search") == {
    "enabled": "auto",
    "threshold_pct": 10,
    "search_default_limit": 5,
    "max_search_limit": 20,
}, data.get("tools", {}).get("tool_search")
assert data.get("agent", {}).get("disabled_toolsets") == ["kanban"]
assert data.get("platform_toolsets", {}).get("telegram") == [
    "vision",
    "image_gen",
    "tts",
    "skills",
    "clarify",
    "nails_onboarding",
    "nails_scheduling",
], data.get("platform_toolsets", {}).get("telegram")

print("CONFIG_POSTSTATE_OK=true")
PY
}

verify_plugin_list_before() {
  local output
  output="$({ HERMES_HOME="$PROFILE" "$HERMES_BIN" --profile nails plugins list --plain --no-bundled; } 2>&1)"

  PLUGIN_LIST_OUTPUT="$output" python3 - <<'PY'
import os

lines = [" ".join(line.split()) for line in os.environ["PLUGIN_LIST_OUTPUT"].splitlines() if line.strip()]
actual = {line for line in lines if "nails-" in line}
expected = {"enabled user 0.5.0 nails-onboarding"}
assert actual == expected, f"unexpected pre-deployment Nails plugins: {sorted(actual)!r}"
print("ONBOARDING_PLUGIN_PRECHECK=true")
PY
}

verify_plugin_list_after() {
  local output
  output="$({ HERMES_HOME="$PROFILE" "$HERMES_BIN" --profile nails plugins list --plain --no-bundled; } 2>&1)"

  PLUGIN_LIST_OUTPUT="$output" python3 - <<'PY'
import os

lines = [" ".join(line.split()) for line in os.environ["PLUGIN_LIST_OUTPUT"].splitlines() if line.strip()]
actual = {line for line in lines if "nails-" in line}
expected = {
    "enabled user 0.5.0 nails-onboarding",
    "enabled user 0.1.0 nails-scheduling",
}
assert actual == expected, f"unexpected post-deployment Nails plugins: {sorted(actual)!r}"
print("PLUGIN_LIST_OK=true")
PY
}

verify_registry_and_visibility() {
  HERMES_HOME="$PROFILE" "$HERMES_PYTHON" - <<'PY'
from hermes_cli.plugins import discover_plugins, get_plugin_manager

# Do not use force=True here. Importing Hermes modules can initialize bundled
# providers; forcing rediscovery in the same interpreter can attempt duplicate
# registration of the built-in dashboard-auth provider named "basic".
discover_plugins()
pm = get_plugin_manager()

from hermes_cli.config import load_config
from hermes_cli.tools_config import _get_platform_tools
from model_tools import get_tool_definitions
from tools.registry import registry

expected_plugins = {
    "nails-onboarding": ("nails-onboarding", "0.5.0"),
    "nails-scheduling": ("nails-scheduling", "0.1.0"),
}
for key, (manifest_name, version) in expected_plugins.items():
    plugin = pm._plugins.get(key)
    assert plugin is not None, f"plugin missing: {key}"
    assert plugin.manifest.name == manifest_name, (key, plugin.manifest.name)
    assert str(plugin.manifest.version) == version, (key, plugin.manifest.version)
    assert plugin.enabled is True, (key, plugin.enabled)
    assert not plugin.error, (key, plugin.error)

actual_toolsets = {
    name for name in registry.get_registered_toolset_names() if "nails" in name
}
expected_toolsets = {"nails_onboarding", "nails_scheduling"}
assert actual_toolsets == expected_toolsets, sorted(actual_toolsets)

actual_tools = {name for name in registry.get_all_tool_names() if "nails" in name}
expected_tools = {"nails_onboarding", "nails_scheduling"}
assert actual_tools == expected_tools, sorted(actual_tools)

cfg = load_config()
# _get_platform_tools returns a set-like, unordered collection in this Hermes
# version. Compare membership, never iteration order.
telegram_toolsets = set(_get_platform_tools(cfg, "telegram"))
expected_telegram_toolsets = {
    "vision",
    "image_gen",
    "tts",
    "skills",
    "clarify",
    "nails_onboarding",
    "nails_scheduling",
}
assert telegram_toolsets == expected_telegram_toolsets, sorted(telegram_toolsets)

definitions = get_tool_definitions(
    enabled_toolsets=sorted(telegram_toolsets),
    quiet_mode=True,
    skip_tool_search_assembly=True,
)
visible = {item["function"]["name"] for item in definitions}
assert "nails_onboarding" in visible, sorted(visible)
assert "nails_scheduling" in visible, sorted(visible)

print("PLUGIN_REGISTRY_OK=true")
print("TELEGRAM_VISIBILITY_OK=true")
PY
}

restore_runtime_from_backup() {
  rm -rf "$PLUGIN_TARGET"
  if [[ "$PLUGIN_EXISTED" == "true" && -e "${BACKUP_DIR}/plugin.before" ]]; then
    cp -a "${BACKUP_DIR}/plugin.before" "$PLUGIN_TARGET"
  fi

  rm -f "$SKILL_TARGET"
  if [[ "$SKILL_EXISTED" == "true" && -e "${BACKUP_DIR}/skill.before" ]]; then
    install -d -o root -g root -m 700 "$(dirname "$SKILL_TARGET")"
    cp -a "${BACKUP_DIR}/skill.before" "$SKILL_TARGET"
  fi

  if [[ -f "${BACKUP_DIR}/config.before" ]]; then
    cp -a "${BACKUP_DIR}/config.before" "$PROFILE_CONFIG"
  fi
}

rollback() {
  local original_rc="${1:-1}"

  set +e
  trap - ERR

  if [[ "$MUTATION_STARTED" != "true" ]]; then
    printf '\nROLLBACK_PERFORMED=false\n'
    printf 'ROLLBACK_REASON=no-production-mutation-started\n'
    return "$original_rc"
  fi

  user_systemctl stop "$GATEWAY" >/dev/null 2>&1 || true
  restore_runtime_from_backup

  if [[ -n "$HEAD_BEFORE" ]]; then
    git -C "$REPO" reset --hard "$HEAD_BEFORE" >/dev/null 2>&1 || true
  fi

  user_systemctl start "$GATEWAY" >/dev/null 2>&1 || true
  for _ in $(seq 1 60); do
    user_systemctl is-active --quiet "$GATEWAY" && break
    sleep 1
  done

  ROLLBACK_PERFORMED="true"
  printf '\nROLLBACK_PERFORMED=true\n'
  printf 'ROLLBACK_TARGET_HEAD=%s\n' "${HEAD_BEFORE:-unknown}"
  printf 'ROLLBACK_HEAD_CURRENT=%s\n' "$(git -C "$REPO" rev-parse HEAD 2>/dev/null || true)"
  printf 'ROLLBACK_GATEWAY_STATE=%s\n' "$(user_systemctl is-active "$GATEWAY" 2>/dev/null || true)"

  return "$original_rc"
}

on_error() {
  local rc="$?"
  local line="$1"

  printf '\nDEPLOYMENT_FAILED=true\n'
  printf 'runbook=%s\n' "$RUNBOOK_ID"
  printf 'failed_line=%s\n' "$line"
  printf 'head_current=%s\n' "$(git -C "$REPO" rev-parse HEAD 2>/dev/null || true)"
  printf 'gateway_state=%s\n' "$(user_systemctl is-active "$GATEWAY" 2>/dev/null || true)"
  if [[ -d "$BACKUP_DIR" ]]; then
    printf 'backup_dir=%s\n' "$BACKUP_DIR"
  else
    printf 'backup_dir=not-created\n'
  fi

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
[[ -f "$PROFILE_CONFIG" ]] || fail "Hermes profile config not found"
[[ ! -L "$PROFILE_CONFIG" ]] || fail "Hermes profile config must not be a symlink"
[[ -x "$HERMES_BIN" ]] || fail "Hermes CLI not found"
[[ -x "$HERMES_PYTHON" ]] || fail "Hermes Python not found"

[[ "$(stat -c '%a %U:%G' "$BACKEND_ENV")" == "600 root:root" ]] \
  || fail "unexpected backend env ownership or mode"
[[ "$(stat -c '%a %U:%G' "$PROFILE_ENV")" == "600 root:root" ]] \
  || fail "unexpected profile env ownership or mode"
[[ "$(stat -c '%a %U:%G' "$PROFILE_CONFIG")" == "600 root:root" ]] \
  || fail "unexpected profile config ownership or mode"

cd "$REPO"
[[ "$(git branch --show-current)" == "main" ]] || fail "production checkout is not on main"
[[ -z "$(git status --porcelain)" ]] || fail "production working tree is not clean"
HEAD_BEFORE="$(git rev-parse HEAD)"
[[ "$HEAD_BEFORE" == "$EXPECTED_BEFORE" ]] || fail "unexpected production HEAD before deployment"

git fetch --quiet origin main
[[ "$(git rev-parse origin/main)" == "$RELEASE_SHA" ]] \
  || fail "origin/main does not equal the approved release SHA"
git cat-file -e "${RELEASE_SHA}^{commit}"
git merge-base --is-ancestor "$EXPECTED_BEFORE" "$RELEASE_SHA" \
  || fail "approved release is not a descendant of production HEAD"
git merge-base --is-ancestor "$EXPECTED_FEATURE_ANCESTOR" "$RELEASE_SHA" \
  || fail "approved release does not contain scheduling implementation"
git merge-base --is-ancestor "$EXPECTED_V2_ANCESTOR" "$RELEASE_SHA" \
  || fail "approved release does not contain the V2 rollback evidence and contracts"
git cat-file -e "${RELEASE_SHA}:ops/deploy/nails-002e4-v3.sh"
git cat-file -e "${RELEASE_SHA}:hermes/plugins/nails_scheduling/plugin.yaml"
git cat-file -e "${RELEASE_SHA}:hermes/skills/nails-scheduling/SKILL.md"

curl -fsS "${API_BASE}/health" >/dev/null
curl -fsS "${API_BASE}/ready" >/dev/null

GATEWAY_LOAD_STATE="$(user_systemctl show "$GATEWAY" -p LoadState --value)"
GATEWAY_ACTIVE_STATE="$(user_systemctl show "$GATEWAY" -p ActiveState --value)"
GATEWAY_SUB_STATE="$(user_systemctl show "$GATEWAY" -p SubState --value)"
GATEWAY_PID_BEFORE="$(user_systemctl show "$GATEWAY" -p MainPID --value)"
GATEWAY_FRAGMENT_ACTUAL="$(user_systemctl show "$GATEWAY" -p FragmentPath --value)"
GATEWAY_UNIT_STATE="$(user_systemctl show "$GATEWAY" -p UnitFileState --value)"
GATEWAY_RESTART_POLICY="$(user_systemctl show "$GATEWAY" -p Restart --value)"

[[ "$GATEWAY_LOAD_STATE" == "loaded" ]] || fail "gateway user unit is not loaded"
[[ "$GATEWAY_ACTIVE_STATE" == "active" ]] || fail "gateway is not active before deployment"
[[ "$GATEWAY_SUB_STATE" == "running" ]] || fail "gateway is not running before deployment"
[[ "$GATEWAY_PID_BEFORE" =~ ^[1-9][0-9]*$ ]] || fail "gateway MainPID is invalid"
[[ "$GATEWAY_FRAGMENT_ACTUAL" == "$GATEWAY_FRAGMENT" ]] || fail "unexpected gateway unit fragment"
[[ "$GATEWAY_UNIT_STATE" == "enabled" ]] || fail "gateway user unit is not enabled"
[[ "$GATEWAY_RESTART_POLICY" == "always" ]] || fail "unexpected gateway restart policy"

GATEWAY_CMDLINE="$(tr '\0' ' ' <"/proc/${GATEWAY_PID_BEFORE}/cmdline")"
[[ "$GATEWAY_CMDLINE" == *"/usr/local/lib/hermes-agent/venv/bin/python -m hermes_cli.main --profile nails gateway run"* ]] \
  || fail "unexpected gateway command line"
GATEWAY_PPID="$(awk '/^PPid:/{print $2}' "/proc/${GATEWAY_PID_BEFORE}/status")"
GATEWAY_PARENT_CMDLINE="$(tr '\0' ' ' <"/proc/${GATEWAY_PPID}/cmdline")"
[[ "$GATEWAY_PARENT_CMDLINE" == *"/usr/lib/systemd/systemd --user"* ]] \
  || fail "gateway is not parented by root user systemd"

HERMES_VERSION_OUTPUT="$($HERMES_BIN --version)"
[[ "$HERMES_VERSION_OUTPUT" == *"Hermes Agent v0.18.2 (2026.7.7.2)"* ]] \
  || fail "unexpected Hermes version"
HERMES_IMPORT_PATH="$($HERMES_PYTHON - <<'PY'
import hermes_cli
print(hermes_cli.__file__)
PY
)"
[[ "$HERMES_IMPORT_PATH" == "/usr/local/lib/hermes-agent/hermes_cli/__init__.py" ]] \
  || fail "unexpected hermes_cli import path"

verify_config_prestate
verify_plugin_list_before
[[ ! -e "$PLUGIN_TARGET" ]] || fail "scheduling plugin runtime target already exists"
[[ ! -e "$SKILL_TARGET" ]] || fail "scheduling skill runtime target already exists"
verify_keys_match

API_CONTAINER_BEFORE="$(docker compose --env-file "$BACKEND_ENV" ps -q nails-api)"
DB_CONTAINER_BEFORE="$(docker compose --env-file "$BACKEND_ENV" ps -q nails-db)"
[[ -n "$API_CONTAINER_BEFORE" ]] || fail "nails-api container was not found"
[[ -n "$DB_CONTAINER_BEFORE" ]] || fail "nails-db container was not found"
API_ID_BEFORE="$(docker inspect -f '{{.Id}}' "$API_CONTAINER_BEFORE")"
API_STARTED_BEFORE="$(docker inspect -f '{{.State.StartedAt}}' "$API_CONTAINER_BEFORE")"
DB_ID_BEFORE="$(docker inspect -f '{{.Id}}' "$DB_CONTAINER_BEFORE")"
DB_STARTED_BEFORE="$(docker inspect -f '{{.State.StartedAt}}' "$DB_CONTAINER_BEFORE")"
DOCKER_PID_BEFORE="$(systemctl show docker -p MainPID --value)"
DOCKER_ACTIVE_SINCE_BEFORE="$(systemctl show docker -p ActiveEnterTimestamp --value)"

printf '== %s: 2. Backup ==\n' "$RUNBOOK_ID"

install -d -o root -g root -m 700 "$BACKUP_DIR"
cp -a "$PROFILE_CONFIG" "${BACKUP_DIR}/config.before"
sha256sum "$PROFILE_CONFIG" >"${BACKUP_DIR}/config.before.sha256"
printf '%s\n' "$HEAD_BEFORE" >"${BACKUP_DIR}/head.before"
printf '%s\n' "$RELEASE_SHA" >"${BACKUP_DIR}/head.approved"
printf '%s\n' "$GATEWAY_PID_BEFORE" >"${BACKUP_DIR}/gateway.pid.before"

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
[[ "$(stat -c '%a %U:%G' "${BACKUP_DIR}/config.before")" == "600 root:root" ]] \
  || fail "config backup ownership or mode is invalid"

printf '== %s: 3. Exact repository update ==\n' "$RUNBOOK_ID"

MUTATION_STARTED="true"
git merge --ff-only "$RELEASE_SHA"
[[ "$(git rev-parse HEAD)" == "$RELEASE_SHA" ]] || fail "unexpected HEAD after fast-forward"
[[ -z "$(git status --porcelain)" ]] || fail "working tree is not clean after fast-forward"

printf '== %s: 4. Validate release sources ==\n' "$RUNBOOK_ID"

[[ -d "$PLUGIN_SOURCE" ]] || fail "scheduling plugin source is missing"
[[ -f "$SKILL_SOURCE" ]] || fail "scheduling skill source is missing"
for file in "${RELEASE_FILES[@]}"; do
  [[ -f "${PLUGIN_SOURCE}/${file}" ]] || fail "missing release file: ${file}"
  [[ ! -L "${PLUGIN_SOURCE}/${file}" ]] || fail "release file is a symlink: ${file}"
done

PLUGIN_SOURCE="$PLUGIN_SOURCE" SKILL_SOURCE="$SKILL_SOURCE" python3 - <<'PY'
import os
from pathlib import Path

plugin = Path(os.environ["PLUGIN_SOURCE"])
skill = Path(os.environ["SKILL_SOURCE"])

manifest = (plugin / "plugin.yaml").read_text(encoding="utf-8")
assert "name: nails-scheduling" in manifest
assert "version: 0.1.0" in manifest
assert "name: NAILS_INTERNAL_API_KEY" in manifest
assert "secret: true" in manifest
assert "  - nails_scheduling" in manifest

register = (plugin / "__init__.py").read_text(encoding="utf-8")
assert 'name="nails_scheduling"' in register
assert 'toolset="nails_scheduling"' in register

skill_text = skill.read_text(encoding="utf-8")
assert "Думаю… (nails_scheduling)" in skill_text
assert "create_client" in skill_text
assert "create_booking" in skill_text

print("STATIC_RELEASE_VALIDATION=true")
PY

printf '== %s: 5. Stop only the root user-level Nails gateway ==\n' "$RUNBOOK_ID"

user_systemctl stop "$GATEWAY"
for _ in $(seq 1 30); do
  CURRENT_PID="$(user_systemctl show "$GATEWAY" -p MainPID --value 2>/dev/null || true)"
  [[ "$CURRENT_PID" == "0" || -z "$CURRENT_PID" ]] && break
  sleep 1
done

GATEWAY_STOP_PID="$(user_systemctl show "$GATEWAY" -p MainPID --value 2>/dev/null || true)"
GATEWAY_STOP_STATE="$(user_systemctl is-active "$GATEWAY" 2>/dev/null || true)"
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

printf '== %s: 7. Update structured Hermes YAML ==\n' "$RUNBOOK_ID"

PROFILE_CONFIG="$PROFILE_CONFIG" "$HERMES_PYTHON" - <<'PY'
import copy
import os
import stat
import tempfile
from pathlib import Path

import yaml

path = Path(os.environ["PROFILE_CONFIG"])
original_stat = path.stat()
data = yaml.safe_load(path.read_text(encoding="utf-8"))
assert isinstance(data, dict)
assert data.get("plugins", {}).get("enabled") == ["nails-onboarding"]
assert data.get("platform_toolsets", {}).get("telegram") == [
    "vision",
    "image_gen",
    "tts",
    "skills",
    "clarify",
    "nails_onboarding",
]

expected = copy.deepcopy(data)
expected["plugins"]["enabled"].append("nails-scheduling")
expected["platform_toolsets"]["telegram"].append("nails_scheduling")

rendered = yaml.safe_dump(
    expected,
    allow_unicode=True,
    default_flow_style=False,
    sort_keys=False,
)

fd, temp_name = tempfile.mkstemp(prefix="config.yaml.", dir=str(path.parent), text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp_name, stat.S_IMODE(original_stat.st_mode))
    os.chown(temp_name, original_stat.st_uid, original_stat.st_gid)
    os.replace(temp_name, path)
finally:
    if os.path.exists(temp_name):
        os.unlink(temp_name)

reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
assert reloaded == expected
print("CONFIG_UPDATED_ATOMICALLY=true")
PY

verify_config_poststate
[[ "$(stat -c '%a %U:%G' "$PROFILE_CONFIG")" == "600 root:root" ]] \
  || fail "profile config ownership or mode changed"
HERMES_HOME="$PROFILE" "$HERMES_BIN" --profile nails config check >/dev/null

printf '== %s: 8. Verify runtime and registration before restart ==\n' "$RUNBOOK_ID"

EXPECTED_FILES="$(printf '%s\n' "${RELEASE_FILES[@]}" | LC_ALL=C sort)"
ACTUAL_FILES="$(find "$PLUGIN_TARGET" -mindepth 1 -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort)"
[[ "$ACTUAL_FILES" == "$EXPECTED_FILES" ]] || fail "runtime plugin contains unexpected or missing files"
[[ -z "$(find "$PLUGIN_TARGET" -mindepth 1 -maxdepth 1 ! -type f -print -quit)" ]] \
  || fail "runtime plugin contains a non-file entry"
[[ "$(stat -c '%a %U:%G' "$PLUGIN_TARGET")" == "700 root:root" ]] \
  || fail "runtime plugin directory ownership or mode is invalid"

for file in "${RELEASE_FILES[@]}"; do
  [[ "$(stat -c '%a %U:%G' "${PLUGIN_TARGET}/${file}")" == "600 root:root" ]] \
    || fail "invalid runtime ownership or mode: ${file}"
  cmp -s "${PLUGIN_SOURCE}/${file}" "${PLUGIN_TARGET}/${file}" \
    || fail "source/target mismatch: ${file}"
done
[[ "$(stat -c '%a %U:%G' "$SKILL_TARGET")" == "600 root:root" ]] \
  || fail "runtime skill ownership or mode is invalid"
cmp -s "$SKILL_SOURCE" "$SKILL_TARGET" || fail "scheduling skill source/target mismatch"

verify_plugin_list_after
verify_registry_and_visibility
verify_keys_match

printf '== %s: 9. Start only the root user-level Nails gateway ==\n' "$RUNBOOK_ID"

user_systemctl start "$GATEWAY"
for _ in $(seq 1 60); do
  user_systemctl is-active --quiet "$GATEWAY" && break
  sleep 1
done
user_systemctl is-active --quiet "$GATEWAY" || fail "gateway did not become active"

GATEWAY_LOAD_AFTER="$(user_systemctl show "$GATEWAY" -p LoadState --value)"
GATEWAY_ACTIVE_AFTER="$(user_systemctl show "$GATEWAY" -p ActiveState --value)"
GATEWAY_SUB_AFTER="$(user_systemctl show "$GATEWAY" -p SubState --value)"
GATEWAY_PID_AFTER="$(user_systemctl show "$GATEWAY" -p MainPID --value)"
GATEWAY_FRAGMENT_AFTER="$(user_systemctl show "$GATEWAY" -p FragmentPath --value)"

[[ "$GATEWAY_LOAD_AFTER" == "loaded" ]] || fail "gateway is not loaded after deployment"
[[ "$GATEWAY_ACTIVE_AFTER" == "active" ]] || fail "gateway is not active after deployment"
[[ "$GATEWAY_SUB_AFTER" == "running" ]] || fail "gateway is not running after deployment"
[[ "$GATEWAY_PID_AFTER" =~ ^[1-9][0-9]*$ ]] || fail "gateway MainPID is invalid after deployment"
[[ "$GATEWAY_PID_AFTER" != "$GATEWAY_PID_BEFORE" ]] || fail "gateway PID did not change"
[[ "$GATEWAY_FRAGMENT_AFTER" == "$GATEWAY_FRAGMENT" ]] || fail "gateway fragment changed"

sleep 3
GATEWAY_LOG="${BACKUP_DIR}/gateway-after-deployment.log"
user_journalctl -u "$GATEWAY" --since "$LOG_SINCE" --no-pager >"$GATEWAY_LOG"
chmod 600 "$GATEWAY_LOG"
chown root:root "$GATEWAY_LOG"

if grep -Eiq \
  'traceback|importerror|modulenotfounderror|syntaxerror|manifest[^[:alnum:]]+error|plugin[^[:alnum:]]+error|missing[^[:alnum:]]+NAILS_INTERNAL_API_KEY|polling conflict|unauthorized|config[^[:alnum:]]+error' \
  "$GATEWAY_LOG"
then
  fail "gateway log contains a plugin/import/configuration error"
fi

ONBOARDING_LOG_MENTIONS="$(grep -Eic 'nails[-_]onboarding' "$GATEWAY_LOG" || true)"
SCHEDULING_LOG_MENTIONS="$(grep -Eic 'nails[-_]scheduling' "$GATEWAY_LOG" || true)"

verify_plugin_list_after
verify_registry_and_visibility
verify_keys_match

printf '== %s: 10. Verify backend and Docker unchanged ==\n' "$RUNBOOK_ID"

API_CONTAINER_AFTER="$(docker compose --env-file "$BACKEND_ENV" ps -q nails-api)"
DB_CONTAINER_AFTER="$(docker compose --env-file "$BACKEND_ENV" ps -q nails-db)"
[[ -n "$API_CONTAINER_AFTER" ]] || fail "nails-api container disappeared"
[[ -n "$DB_CONTAINER_AFTER" ]] || fail "nails-db container disappeared"
API_ID_AFTER="$(docker inspect -f '{{.Id}}' "$API_CONTAINER_AFTER")"
API_STARTED_AFTER="$(docker inspect -f '{{.State.StartedAt}}' "$API_CONTAINER_AFTER")"
DB_ID_AFTER="$(docker inspect -f '{{.Id}}' "$DB_CONTAINER_AFTER")"
DB_STARTED_AFTER="$(docker inspect -f '{{.State.StartedAt}}' "$DB_CONTAINER_AFTER")"
DOCKER_PID_AFTER="$(systemctl show docker -p MainPID --value)"
DOCKER_ACTIVE_SINCE_AFTER="$(systemctl show docker -p ActiveEnterTimestamp --value)"

[[ "$API_ID_AFTER" == "$API_ID_BEFORE" ]] || fail "nails-api container changed"
[[ "$API_STARTED_AFTER" == "$API_STARTED_BEFORE" ]] || fail "nails-api StartedAt changed"
[[ "$DB_ID_AFTER" == "$DB_ID_BEFORE" ]] || fail "nails-db container changed"
[[ "$DB_STARTED_AFTER" == "$DB_STARTED_BEFORE" ]] || fail "nails-db StartedAt changed"
[[ "$DOCKER_PID_AFTER" == "$DOCKER_PID_BEFORE" ]] || fail "Docker daemon PID changed"
[[ "$DOCKER_ACTIVE_SINCE_AFTER" == "$DOCKER_ACTIVE_SINCE_BEFORE" ]] \
  || fail "Docker daemon active timestamp changed"

curl -fsS "${API_BASE}/health" >/dev/null
curl -fsS "${API_BASE}/ready" >/dev/null
[[ "$(git rev-parse HEAD)" == "$RELEASE_SHA" ]] || fail "final repository HEAD changed"
[[ -z "$(git status --porcelain)" ]] || fail "final repository working tree is not clean"

trap - ERR

printf '\nNAILS_002E4_V3_DEPLOYMENT_OK\n'
printf 'runbook=%s\n' "$RUNBOOK_ID"
printf 'hostname=%s\n' "$(hostname -f)"
printf 'head_before=%s\n' "$HEAD_BEFORE"
printf 'head_after=%s\n' "$(git rev-parse HEAD)"
printf 'git_tree_clean=true\n'
printf 'backup_dir=%s\n' "$BACKUP_DIR"
printf 'plugins_enabled=nails-onboarding,nails-scheduling\n'
printf 'telegram_toolsets_membership=clarify,image_gen,nails_onboarding,nails_scheduling,skills,tts,vision\n'
printf 'plugin_source_target_match=true\n'
printf 'skill_source_target_match=true\n'
printf 'runtime_release_files_only=true\n'
printf 'gateway_manager=root-user-systemd\n'
printf 'gateway_fragment=%s\n' "$GATEWAY_FRAGMENT_AFTER"
printf 'gateway_pid_before=%s\n' "$GATEWAY_PID_BEFORE"
printf 'gateway_stop_state=%s\n' "$GATEWAY_STOP_STATE"
printf 'gateway_pid_after=%s\n' "$GATEWAY_PID_AFTER"
printf 'gateway_state=%s\n' "$(user_systemctl is-active "$GATEWAY")"
printf 'gateway_error_scan=clean\n'
printf 'gateway_nails_onboarding_log_mentions=%s\n' "$ONBOARDING_LOG_MENTIONS"
printf 'gateway_nails_scheduling_log_mentions=%s\n' "$SCHEDULING_LOG_MENTIONS"
printf 'plugin_discovery=idempotent\n'
printf 'plugin_registry=ok\n'
printf 'telegram_visibility=ok\n'
printf 'backend_api_container_unchanged=true\n'
printf 'backend_db_container_unchanged=true\n'
printf 'docker_daemon_unchanged=true\n'
printf 'backend_health=ok\n'
printf 'backend_ready=ok\n'
printf 'migration_executed=false\n'
printf 'database_write_executed=false\n'
printf 'backend_restart_executed=false\n'
printf 'rollback_performed=%s\n' "$ROLLBACK_PERFORMED"
