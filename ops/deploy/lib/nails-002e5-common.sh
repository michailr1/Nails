#!/usr/bin/env bash

RUNBOOK_ID="NAILS-002E5"
EXPECTED_HOST="de.funti.cc"
EXPECTED_BEFORE="385a92962e3736553335d717adcdf4b83ac8a8b3"
EXPECTED_CODE_ANCESTOR="c9e400c80398bd4367aad0ed0416ee0fc6a79b2d"

BACKEND_ENV="/opt/nails/.env"
API_BASE="http://127.0.0.1:8210"
PROFILE="/root/.hermes/profiles/nails"
PROFILE_ENV="${PROFILE}/.env"
PROFILE_CONFIG="${PROFILE}/config.yaml"
HERMES_ROOT="/usr/local/lib/hermes-agent"
HERMES_BIN="${HERMES_ROOT}/venv/bin/hermes"
HERMES_PYTHON="${HERMES_ROOT}/venv/bin/python"
GATEWAY="hermes-gateway-nails.service"
GATEWAY_FRAGMENT="/root/.config/systemd/user/hermes-gateway-nails.service"
USER_RUNTIME_DIR="/run/user/0"

PLUGIN_SOURCE="${REPO}/hermes/plugins/nails_scheduling"
PLUGIN_TARGET="${PROFILE}/plugins/nails_scheduling"
ONBOARDING_SKILL_SOURCE="${REPO}/hermes/skills/nails-onboarding/SKILL.md"
ONBOARDING_SKILL_TARGET="${PROFILE}/skills/nails-onboarding/SKILL.md"
SCHEDULING_SKILL_SOURCE="${REPO}/hermes/skills/nails-scheduling/SKILL.md"
SCHEDULING_SKILL_TARGET="${PROFILE}/skills/nails-scheduling/SKILL.md"

PLUGIN_FILES=(
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
BACKUP_ROOT="/opt/nails/backups"
DB_BACKUP="${BACKUP_ROOT}/nails-before-002e5-${STAMP}.sql.gz"
RUNTIME_BACKUP="${PROFILE}/backups/nails-002e5-${STAMP}"
LOG_SINCE="$(date '+%Y-%m-%d %H:%M:%S')"

HEAD_BEFORE=""
MUTATION_STARTED="false"
IMAGE_BUILT="false"
API_RECREATED="false"
ROLLBACK_PERFORMED="false"

API_CONTAINER_BEFORE=""
API_CONTAINER_AFTER=""
API_ID_BEFORE=""
API_ID_AFTER=""
API_STARTED_BEFORE=""
API_STARTED_AFTER=""
API_IMAGE_ID_BEFORE=""
API_IMAGE_REF_BEFORE=""
API_IMAGE_ID_AFTER_BUILD=""
DB_CONTAINER_BEFORE=""
DB_ID_BEFORE=""
DB_STARTED_BEFORE=""
DOCKER_PID_BEFORE=""
DOCKER_ACTIVE_SINCE_BEFORE=""
GATEWAY_PID_BEFORE=""
GATEWAY_PID_AFTER=""

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  return 1
}

compose() {
  docker compose --env-file "$BACKEND_ENV" "$@"
}

user_systemctl() {
  XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" systemctl --user "$@"
}

user_journalctl() {
  XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" journalctl --user "$@"
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
  [[ ${#backend_key} -ge 32 ]] || fail "backend internal key is missing or too short"
  [[ ${#profile_key} -ge 32 ]] || fail "profile internal key is missing or too short"
  BACKEND_KEY="$backend_key" PROFILE_KEY="$profile_key" python3 - <<'PY'
import hmac
import os

if not hmac.compare_digest(os.environ["BACKEND_KEY"], os.environ["PROFILE_KEY"]):
    raise SystemExit("gateway/backend keys do not match")
print("KEYS_MATCH=true")
PY
  unset backend_key profile_key
}

verify_config() {
  PROFILE_CONFIG="$PROFILE_CONFIG" "$HERMES_PYTHON" - <<'PY'
import os
from pathlib import Path

import yaml

path = Path(os.environ["PROFILE_CONFIG"])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
assert isinstance(data, dict), type(data)
plugins = data.get("plugins")
assert isinstance(plugins, dict), plugins
assert plugins.get("enabled") == ["nails-onboarding", "nails-scheduling"]
assert plugins.get("disabled") == []
assert plugins.get("entries") == {
    "nails-onboarding": {"allow_tool_override": False},
}
assert data.get("toolsets") == ["hermes-cli"]
assert "custom_toolsets" not in data
assert data.get("tools", {}).get("tool_search") == {
    "enabled": "auto",
    "threshold_pct": 10,
    "search_default_limit": 5,
    "max_search_limit": 20,
}
assert data.get("agent", {}).get("disabled_toolsets") == ["kanban"]
assert data.get("platform_toolsets", {}).get("telegram") == [
    "vision",
    "image_gen",
    "tts",
    "skills",
    "clarify",
    "nails_onboarding",
    "nails_scheduling",
]
print("CONFIG_OK=true")
PY
}

verify_plugin_list() {
  local expected_version="$1"
  local output
  output="$({ HERMES_HOME="$PROFILE" "$HERMES_BIN" --profile nails plugins list --plain --no-bundled; } 2>&1)"
  PLUGIN_LIST_OUTPUT="$output" EXPECTED_VERSION="$expected_version" python3 - <<'PY'
import os

lines = [" ".join(line.split()) for line in os.environ["PLUGIN_LIST_OUTPUT"].splitlines() if line.strip()]
actual = {line for line in lines if "nails-" in line}
expected = {
    "enabled user 0.5.0 nails-onboarding",
    f"enabled user {os.environ['EXPECTED_VERSION']} nails-scheduling",
}
assert actual == expected, f"unexpected Nails plugins: {sorted(actual)!r}"
print("PLUGIN_LIST_OK=true")
PY
}

verify_registry_and_visibility() {
  HERMES_HOME="$PROFILE" "$HERMES_PYTHON" - <<'PY'
from hermes_cli.plugins import discover_plugins, get_plugin_manager

discover_plugins()
pm = get_plugin_manager()
from hermes_cli.config import load_config
from hermes_cli.tools_config import _get_platform_tools
from model_tools import get_tool_definitions
from tools.registry import registry

expected = {
    "nails-onboarding": ("nails-onboarding", "0.5.0"),
    "nails-scheduling": ("nails-scheduling", "0.2.0"),
}
for key, (manifest_name, version) in expected.items():
    plugin = pm._plugins.get(key)
    assert plugin is not None, key
    assert plugin.manifest.name == manifest_name
    assert str(plugin.manifest.version) == version
    assert plugin.enabled is True
    assert not plugin.error

assert {name for name in registry.get_registered_toolset_names() if "nails" in name} == {
    "nails_onboarding",
    "nails_scheduling",
}
assert {name for name in registry.get_all_tool_names() if "nails" in name} == {
    "nails_onboarding",
    "nails_scheduling",
}
cfg = load_config()
telegram_toolsets = set(_get_platform_tools(cfg, "telegram"))
assert telegram_toolsets == {
    "vision",
    "image_gen",
    "tts",
    "skills",
    "clarify",
    "nails_onboarding",
    "nails_scheduling",
}
definitions = get_tool_definitions(
    enabled_toolsets=sorted(telegram_toolsets),
    quiet_mode=True,
    skip_tool_search_assembly=True,
)
by_name = {item["function"]["name"]: item for item in definitions}
actions = by_name["nails_scheduling"]["function"]["parameters"]["properties"]["action"]["enum"]
assert "resolve_date" in actions
assert "update_availability" in actions
print("PLUGIN_REGISTRY_OK=true")
print("TELEGRAM_VISIBILITY_OK=true")
print("SCHEDULING_ACTIONS_OK=true")
PY
}

verify_alembic_0006() {
  local output
  output="$(compose exec -T nails-api alembic current 2>&1)"
  grep -Eq '0006.*head' <<<"$output" || fail "Alembic is not at 0006 head"
}

wait_api() {
  local container_id health
  for _ in $(seq 1 90); do
    container_id="$(compose ps -q nails-api 2>/dev/null || true)"
    if [[ -n "$container_id" ]]; then
      health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
      if [[ "$health" == "healthy" ]] \
        && curl -fsS "${API_BASE}/health" >/dev/null 2>&1 \
        && curl -fsS "${API_BASE}/ready" >/dev/null 2>&1
      then
        printf '%s' "$container_id"
        return 0
      fi
    fi
    sleep 2
  done
  fail "nails-api did not become healthy and ready"
}

verify_openapi() {
  local openapi_file="${RUNTIME_BACKUP}/openapi-after.json"
  curl -fsS "${API_BASE}/openapi.json" >"$openapi_file"
  chmod 600 "$openapi_file"
  OPENAPI_FILE="$openapi_file" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["OPENAPI_FILE"]).read_text(encoding="utf-8"))
paths = payload.get("paths", {})
assert "post" in paths["/api/v1/scheduling/date/resolve"]
assert "put" in paths["/api/v1/scheduling/availability"]
assert "get" in paths["/api/v1/scheduling/day"]
assert "get" in paths["/api/v1/scheduling/slots"]
print("OPENAPI_ROUTES_OK=true")
PY
}

restore_runtime() {
  rm -rf "$PLUGIN_TARGET"
  cp -a "${RUNTIME_BACKUP}/plugin.before" "$PLUGIN_TARGET"
  cp -a "${RUNTIME_BACKUP}/onboarding-skill.before" "$ONBOARDING_SKILL_TARGET"
  cp -a "${RUNTIME_BACKUP}/scheduling-skill.before" "$SCHEDULING_SKILL_TARGET"
  cp -a "${RUNTIME_BACKUP}/config.before" "$PROFILE_CONFIG"
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
  [[ -d "$RUNTIME_BACKUP" ]] && restore_runtime
  [[ -n "$HEAD_BEFORE" ]] && git -C "$REPO" reset --hard "$HEAD_BEFORE" >/dev/null 2>&1

  if [[ "$IMAGE_BUILT" == "true" && -n "$API_IMAGE_ID_BEFORE" && -n "$API_IMAGE_REF_BEFORE" ]]; then
    docker image tag "$API_IMAGE_ID_BEFORE" "$API_IMAGE_REF_BEFORE" >/dev/null 2>&1 || true
  fi
  if [[ "$API_RECREATED" == "true" ]]; then
    cd "$REPO" || true
    compose up -d --no-deps --force-recreate --no-build nails-api >/dev/null 2>&1 || true
    wait_api >/dev/null 2>&1 || true
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
  printf 'ROLLBACK_API_HEALTH=%s\n' "$(curl -fsS "${API_BASE}/health" 2>/dev/null || true)"
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
  printf 'database_backup=%s\n' "$DB_BACKUP"
  printf 'runtime_backup=%s\n' "$RUNTIME_BACKUP"
  rollback "$rc"
  exit "$rc"
}
