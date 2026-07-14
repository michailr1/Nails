#!/usr/bin/env bash

source <(git -C "$REPO" show "${RELEASE_SHA}:ops/deploy/lib/nails-002e5-common.sh")

RUNBOOK_ID="NAILS-002E6"
BASELINE_E4="385a92962e3736553335d717adcdf4b83ac8a8b3"
BASELINE_E5="a0ef8c5c26301a9f6950544afd0e070b7e691582"
EXPECTED_CODE_ANCESTOR="06d68faf69eb6828360c1ccc9b0d8c83e14a0eb9"
DB_BACKUP="${BACKUP_ROOT}/nails-before-002e6-${STAMP}.sql.gz"
RUNTIME_BACKUP="${PROFILE}/backups/nails-002e6-${STAMP}"
PRE_PLUGIN_VERSION=""

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
    "nails-scheduling": ("nails-scheduling", "0.3.0"),
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

scheduling_actions = set(
    by_name["nails_scheduling"]["function"]["parameters"]["properties"]["action"]["enum"]
)
required_scheduling = {
    "resolve_date",
    "list_services",
    "find_service",
    "create_service",
    "update_service",
    "day_view",
    "free_slots",
    "find_client",
    "create_client",
    "update_availability",
    "create_booking",
}
assert scheduling_actions == required_scheduling, sorted(scheduling_actions)

onboarding_actions = set(
    by_name["nails_onboarding"]["function"]["parameters"]["properties"]["action"]["enum"]
)
required_preferences = {
    "get_master_preferences",
    "save_master_name",
    "save_master_style",
    "save_default_work_hours",
}
assert required_preferences.issubset(onboarding_actions), sorted(onboarding_actions)

print("PLUGIN_REGISTRY_OK=true")
print("TELEGRAM_VISIBILITY_OK=true")
print("SCHEDULING_ACTIONS_OK=true")
print("MASTER_PREFERENCES_ACTIONS_OK=true")
PY
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
expected = {
    "/api/v1/scheduling/date/resolve": "post",
    "/api/v1/scheduling/availability": "put",
    "/api/v1/scheduling/services": {"get", "post", "put"},
    "/api/v1/scheduling/services/exact": "get",
    "/api/v1/scheduling/day": "get",
    "/api/v1/scheduling/slots": "get",
    "/api/v1/onboarding/preferences": "get",
    "/api/v1/onboarding/preferences/name": "put",
    "/api/v1/onboarding/preferences/style": "put",
    "/api/v1/onboarding/preferences/default-work-hours": "put",
}
for path, methods in expected.items():
    assert path in paths, path
    required = {methods} if isinstance(methods, str) else methods
    assert required.issubset(paths[path]), (path, sorted(paths[path]))
print("OPENAPI_ROUTES_OK=true")
PY
}

nails_002e6_main() {
  trap 'on_error "$LINENO"' ERR

  printf '== %s: 1. Preflight ==\n' "$RUNBOOK_ID"

  [[ "$(id -u)" -eq 0 ]] || fail "runbook must be executed as root"
  [[ "$(hostname -f)" == "$EXPECTED_HOST" ]] || fail "unexpected hostname"
  [[ -d "$REPO/.git" ]] || fail "repository checkout not found"
  [[ -f "$BACKEND_ENV" ]] || fail "backend environment file not found"
  [[ -d "$PROFILE" ]] || fail "Hermes profile not found"
  [[ -f "$PROFILE_ENV" ]] || fail "Hermes profile environment file not found"
  [[ -f "$PROFILE_CONFIG" ]] || fail "Hermes profile config not found"
  [[ -x "$HERMES_BIN" && -x "$HERMES_PYTHON" ]] || fail "Hermes runtime not found"
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
  case "$HEAD_BEFORE" in
    "$BASELINE_E4") PRE_PLUGIN_VERSION="0.1.0" ;;
    "$BASELINE_E5") PRE_PLUGIN_VERSION="0.2.0" ;;
    *) fail "production HEAD is not an approved E4 or E5 baseline" ;;
  esac

  git fetch --quiet origin main
  [[ "$(git rev-parse origin/main)" == "$RELEASE_SHA" ]] \
    || fail "origin/main does not equal approved release SHA"
  git cat-file -e "${RELEASE_SHA}^{commit}"
  git merge-base --is-ancestor "$HEAD_BEFORE" "$RELEASE_SHA" \
    || fail "release is not a descendant of production"
  git merge-base --is-ancestor "$EXPECTED_CODE_ANCESTOR" "$RELEASE_SHA" \
    || fail "release does not contain reviewed combined operations and preferences code"
  git cat-file -e "${RELEASE_SHA}:ops/deploy/nails-002e6-combined-operations.sh"
  git cat-file -e "${RELEASE_SHA}:ops/deploy/lib/nails-002e6-runtime.sh"
  git diff --quiet "$HEAD_BEFORE" "$RELEASE_SHA" -- backend/alembic \
    || fail "release unexpectedly changes Alembic files"

  curl -fsS "${API_BASE}/health" >/dev/null
  curl -fsS "${API_BASE}/ready" >/dev/null
  verify_alembic_0006

  API_CONTAINER_BEFORE="$(compose ps -q nails-api)"
  DB_CONTAINER_BEFORE="$(compose ps -q nails-db)"
  [[ -n "$API_CONTAINER_BEFORE" && -n "$DB_CONTAINER_BEFORE" ]] \
    || fail "backend containers were not found"
  API_ID_BEFORE="$(docker inspect -f '{{.Id}}' "$API_CONTAINER_BEFORE")"
  API_STARTED_BEFORE="$(docker inspect -f '{{.State.StartedAt}}' "$API_CONTAINER_BEFORE")"
  API_IMAGE_ID_BEFORE="$(docker inspect -f '{{.Image}}' "$API_CONTAINER_BEFORE")"
  API_IMAGE_REF_BEFORE="$(docker inspect -f '{{.Config.Image}}' "$API_CONTAINER_BEFORE")"
  [[ -n "$API_IMAGE_ID_BEFORE" && -n "$API_IMAGE_REF_BEFORE" ]] \
    || fail "could not identify current API image"
  DB_ID_BEFORE="$(docker inspect -f '{{.Id}}' "$DB_CONTAINER_BEFORE")"
  DB_STARTED_BEFORE="$(docker inspect -f '{{.State.StartedAt}}' "$DB_CONTAINER_BEFORE")"
  DOCKER_PID_BEFORE="$(systemctl show docker -p MainPID --value)"
  DOCKER_ACTIVE_SINCE_BEFORE="$(systemctl show docker -p ActiveEnterTimestamp --value)"

  GATEWAY_PID_BEFORE="$(user_systemctl show "$GATEWAY" -p MainPID --value)"
  [[ "$(user_systemctl show "$GATEWAY" -p LoadState --value)" == "loaded" ]]
  [[ "$(user_systemctl show "$GATEWAY" -p ActiveState --value)" == "active" ]]
  [[ "$(user_systemctl show "$GATEWAY" -p SubState --value)" == "running" ]]
  [[ "$GATEWAY_PID_BEFORE" =~ ^[1-9][0-9]*$ ]]
  [[ "$(user_systemctl show "$GATEWAY" -p FragmentPath --value)" == "$GATEWAY_FRAGMENT" ]]
  [[ "$(user_systemctl show "$GATEWAY" -p UnitFileState --value)" == "enabled" ]]
  [[ "$(user_systemctl show "$GATEWAY" -p Restart --value)" == "always" ]]

  HERMES_VERSION_OUTPUT="$($HERMES_BIN --version)"
  [[ "$HERMES_VERSION_OUTPUT" == *"Hermes Agent v0.18.2 (2026.7.7.2)"* ]] \
    || fail "unexpected Hermes version"
  verify_config
  verify_plugin_list "$PRE_PLUGIN_VERSION"
  verify_keys_match

  [[ -d "$PLUGIN_TARGET" ]] || fail "scheduling runtime plugin missing"
  [[ -f "$ONBOARDING_SKILL_TARGET" ]] || fail "onboarding runtime skill missing"
  [[ -f "$SCHEDULING_SKILL_TARGET" ]] || fail "scheduling runtime skill missing"
  for file in "${PLUGIN_FILES[@]}"; do
    cmp -s "${PLUGIN_SOURCE}/${file}" "${PLUGIN_TARGET}/${file}" \
      || fail "current scheduling source/runtime mismatch: ${file}"
  done
  cmp -s "$ONBOARDING_SKILL_SOURCE" "$ONBOARDING_SKILL_TARGET" \
    || fail "current onboarding skill source/runtime mismatch"
  cmp -s "$SCHEDULING_SKILL_SOURCE" "$SCHEDULING_SKILL_TARGET" \
    || fail "current scheduling skill source/runtime mismatch"

  printf '== %s: 2. Backups ==\n' "$RUNBOOK_ID"

  install -d -o root -g root -m 700 "$BACKUP_ROOT"
  install -d -o root -g root -m 700 "$RUNTIME_BACKUP"
  cp -a "$PROFILE_CONFIG" "${RUNTIME_BACKUP}/config.before"
  cp -a "$PLUGIN_TARGET" "${RUNTIME_BACKUP}/plugin.before"
  cp -a "$ONBOARDING_SKILL_TARGET" "${RUNTIME_BACKUP}/onboarding-skill.before"
  cp -a "$SCHEDULING_SKILL_TARGET" "${RUNTIME_BACKUP}/scheduling-skill.before"
  printf '%s\n' "$HEAD_BEFORE" >"${RUNTIME_BACKUP}/head.before"
  printf '%s\n' "$PRE_PLUGIN_VERSION" >"${RUNTIME_BACKUP}/plugin-version.before"
  printf '%s\n' "$API_IMAGE_ID_BEFORE" >"${RUNTIME_BACKUP}/api-image-id.before"
  printf '%s\n' "$API_IMAGE_REF_BEFORE" >"${RUNTIME_BACKUP}/api-image-ref.before"

  compose exec -T nails-db sh -ec \
    'exec pg_dump --no-owner --no-acl --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
    | gzip -9 >"$DB_BACKUP"
  chmod 600 "$DB_BACKUP"
  chown root:root "$DB_BACKUP"
  gzip -t "$DB_BACKUP"
  [[ -s "$DB_BACKUP" ]] || fail "database backup is empty"

  printf '== %s: 3. Exact repository update and release validation ==\n' "$RUNBOOK_ID"

  MUTATION_STARTED="true"
  git merge --ff-only "$RELEASE_SHA"
  [[ "$(git rev-parse HEAD)" == "$RELEASE_SHA" ]]
  [[ -z "$(git status --porcelain)" ]]

  python3 - <<'PY'
from pathlib import Path

root = Path("/opt/nails/repo")
manifest = (root / "hermes/plugins/nails_scheduling/plugin.yaml").read_text(encoding="utf-8")
assert "name: nails-scheduling" in manifest
assert "version: 0.3.0" in manifest
api = (root / "backend/app/api/scheduling.py").read_text(encoding="utf-8")
for route in ('"/date/resolve"', '"/availability"', '"/services"', '"/services/exact"'):
    assert route in api, route
schemas = (root / "hermes/plugins/nails_scheduling/schemas.py").read_text(encoding="utf-8")
for action in (
    '"resolve_date"',
    '"update_availability"',
    '"find_service"',
    '"create_service"',
    '"update_service"',
):
    assert action in schemas, action
scheduling_skill = (root / "hermes/skills/nails-scheduling/SKILL.md").read_text(encoding="utf-8")
assert "никогда не вычисляет дату, год или день недели самостоятельно" in scheduling_skill
assert "никогда не нужно проходить заново ради изменения услуг" in scheduling_skill
assert "## Настройки мастера" in scheduling_skill
assert "не вызывай save-действие до подтверждения" in scheduling_skill
assert "для «ты/вы» не меняй базовый `assistant_style`" in scheduling_skill
assert "не придумывай время окончания" in scheduling_skill
onboarding_skill = (root / "hermes/skills/nails-onboarding/SKILL.md").read_text(encoding="utf-8")
assert "не предлагай перезапуск настройки для изменения графика или услуг" in onboarding_skill
print("STATIC_RELEASE_VALIDATION=true")
print("MASTER_PREFERENCES_SKILL_OK=true")
PY

  printf '== %s: 4. Build new API image while old API stays online ==\n' "$RUNBOOK_ID"

  compose build nails-api
  IMAGE_BUILT="true"
  API_IMAGE_ID_AFTER_BUILD="$(compose images -q nails-api | head -n1)"
  [[ -n "$API_IMAGE_ID_AFTER_BUILD" ]] || fail "new API image was not produced"

  printf '== %s: 5. Stop only the root user-level Nails gateway ==\n' "$RUNBOOK_ID"

  user_systemctl stop "$GATEWAY"
  for _ in $(seq 1 30); do
    current_pid="$(user_systemctl show "$GATEWAY" -p MainPID --value 2>/dev/null || true)"
    [[ "$current_pid" == "0" || -z "$current_pid" ]] && break
    sleep 1
  done
  [[ "$(user_systemctl show "$GATEWAY" -p MainPID --value 2>/dev/null || true)" == "0" ]]

  printf '== %s: 6. Recreate only nails-api ==\n' "$RUNBOOK_ID"

  compose up -d --no-deps --force-recreate --no-build nails-api
  API_RECREATED="true"
  API_CONTAINER_AFTER="$(wait_api)"
  API_ID_AFTER="$(docker inspect -f '{{.Id}}' "$API_CONTAINER_AFTER")"
  API_STARTED_AFTER="$(docker inspect -f '{{.State.StartedAt}}' "$API_CONTAINER_AFTER")"
  [[ "$API_ID_AFTER" != "$API_ID_BEFORE" ]] || fail "API container did not change"
  [[ "$API_STARTED_AFTER" != "$API_STARTED_BEFORE" ]] || fail "API StartedAt did not change"
  [[ "$(compose ps -q nails-db)" == "$DB_CONTAINER_BEFORE" ]] || fail "DB container changed"
  [[ "$(docker inspect -f '{{.Id}}' "$DB_CONTAINER_BEFORE")" == "$DB_ID_BEFORE" ]]
  [[ "$(docker inspect -f '{{.State.StartedAt}}' "$DB_CONTAINER_BEFORE")" == "$DB_STARTED_BEFORE" ]]
  verify_alembic_0006
  verify_openapi
  verify_keys_match

  printf '== %s: 7. Install exact scheduling plugin and both skills ==\n' "$RUNBOOK_ID"

  rm -rf "$PLUGIN_TARGET"
  install -d -o root -g root -m 700 "$PLUGIN_TARGET"
  for file in "${PLUGIN_FILES[@]}"; do
    install -o root -g root -m 600 "${PLUGIN_SOURCE}/${file}" "${PLUGIN_TARGET}/${file}"
  done
  install -o root -g root -m 600 "$ONBOARDING_SKILL_SOURCE" "$ONBOARDING_SKILL_TARGET"
  install -o root -g root -m 600 "$SCHEDULING_SKILL_SOURCE" "$SCHEDULING_SKILL_TARGET"

  for file in "${PLUGIN_FILES[@]}"; do
    cmp -s "${PLUGIN_SOURCE}/${file}" "${PLUGIN_TARGET}/${file}"
    [[ "$(stat -c '%a %U:%G' "${PLUGIN_TARGET}/${file}")" == "600 root:root" ]]
  done
  cmp -s "$ONBOARDING_SKILL_SOURCE" "$ONBOARDING_SKILL_TARGET"
  cmp -s "$SCHEDULING_SKILL_SOURCE" "$SCHEDULING_SKILL_TARGET"
  [[ "$(stat -c '%a %U:%G' "$PLUGIN_TARGET")" == "700 root:root" ]]
  [[ "$(stat -c '%a %U:%G' "$ONBOARDING_SKILL_TARGET")" == "600 root:root" ]]
  [[ "$(stat -c '%a %U:%G' "$SCHEDULING_SKILL_TARGET")" == "600 root:root" ]]
  cmp -s "$PROFILE_CONFIG" "${RUNTIME_BACKUP}/config.before" \
    || fail "Hermes config changed unexpectedly"

  verify_config
  HERMES_HOME="$PROFILE" "$HERMES_BIN" --profile nails config check >/dev/null
  verify_plugin_list "0.3.0"
  verify_registry_and_visibility

  printf '== %s: 8. Start only the root user-level Nails gateway ==\n' "$RUNBOOK_ID"

  user_systemctl start "$GATEWAY"
  for _ in $(seq 1 60); do
    user_systemctl is-active --quiet "$GATEWAY" && break
    sleep 1
  done
  user_systemctl is-active --quiet "$GATEWAY" || fail "gateway did not become active"
  GATEWAY_PID_AFTER="$(user_systemctl show "$GATEWAY" -p MainPID --value)"
  [[ "$GATEWAY_PID_AFTER" =~ ^[1-9][0-9]*$ ]]
  [[ "$GATEWAY_PID_AFTER" != "$GATEWAY_PID_BEFORE" ]]
  [[ "$(user_systemctl show "$GATEWAY" -p SubState --value)" == "running" ]]
  [[ "$(user_systemctl show "$GATEWAY" -p FragmentPath --value)" == "$GATEWAY_FRAGMENT" ]]

  sleep 3
  GATEWAY_LOG="${RUNTIME_BACKUP}/gateway-after.log"
  user_journalctl -u "$GATEWAY" --since "$LOG_SINCE" --no-pager >"$GATEWAY_LOG"
  chmod 600 "$GATEWAY_LOG"
  if grep -Eiq \
    'traceback|importerror|modulenotfounderror|syntaxerror|manifest[^[:alnum:]]+error|plugin[^[:alnum:]]+error|missing[^[:alnum:]]+NAILS_INTERNAL_API_KEY|polling conflict|unauthorized|config[^[:alnum:]]+error' \
    "$GATEWAY_LOG"
  then
    fail "gateway log contains a plugin/import/configuration error"
  fi
  verify_plugin_list "0.3.0"
  verify_registry_and_visibility

  printf '== %s: 9. Final isolation and health checks ==\n' "$RUNBOOK_ID"

  [[ "$(compose ps -q nails-api)" == "$API_CONTAINER_AFTER" ]]
  [[ "$(compose ps -q nails-db)" == "$DB_CONTAINER_BEFORE" ]]
  [[ "$(docker inspect -f '{{.Id}}' "$DB_CONTAINER_BEFORE")" == "$DB_ID_BEFORE" ]]
  [[ "$(docker inspect -f '{{.State.StartedAt}}' "$DB_CONTAINER_BEFORE")" == "$DB_STARTED_BEFORE" ]]
  [[ "$(systemctl show docker -p MainPID --value)" == "$DOCKER_PID_BEFORE" ]]
  [[ "$(systemctl show docker -p ActiveEnterTimestamp --value)" == "$DOCKER_ACTIVE_SINCE_BEFORE" ]]
  curl -fsS "${API_BASE}/health" >/dev/null
  curl -fsS "${API_BASE}/ready" >/dev/null
  verify_alembic_0006
  verify_openapi
  verify_keys_match
  [[ "$(git rev-parse HEAD)" == "$RELEASE_SHA" ]]
  [[ -z "$(git status --porcelain)" ]]
  gzip -t "$DB_BACKUP"

  trap - ERR

  printf '\nNAILS_002E6_DEPLOYMENT_OK\n'
  printf 'runbook=%s\n' "$RUNBOOK_ID"
  printf 'hostname=%s\n' "$(hostname -f)"
  printf 'head_before=%s\n' "$HEAD_BEFORE"
  printf 'head_after=%s\n' "$(git rev-parse HEAD)"
  printf 'pre_scheduling_plugin_version=%s\n' "$PRE_PLUGIN_VERSION"
  printf 'scheduling_plugin_version=0.3.0\n'
  printf 'git_tree_clean=true\n'
  printf 'database_backup=%s\n' "$DB_BACKUP"
  printf 'runtime_backup=%s\n' "$RUNTIME_BACKUP"
  printf 'alembic_before=0006\n'
  printf 'alembic_after=0006\n'
  printf 'schema_revision_changed=false\n'
  printf 'api_container_before=%s\n' "$API_CONTAINER_BEFORE"
  printf 'api_container_after=%s\n' "$API_CONTAINER_AFTER"
  printf 'api_container_changed=true\n'
  printf 'db_container_unchanged=true\n'
  printf 'docker_daemon_unchanged=true\n'
  printf 'backend_health=ok\n'
  printf 'backend_ready=ok\n'
  printf 'openapi_date_resolver=ok\n'
  printf 'openapi_availability_update=ok\n'
  printf 'openapi_service_management=ok\n'
  printf 'openapi_master_preferences=ok\n'
  printf 'plugins_enabled=nails-onboarding,nails-scheduling\n'
  printf 'plugin_source_target_match=true\n'
  printf 'onboarding_skill_source_target_match=true\n'
  printf 'scheduling_skill_source_target_match=true\n'
  printf 'master_preferences_skill=ok\n'
  printf 'config_changed=false\n'
  printf 'plugin_registry=ok\n'
  printf 'telegram_visibility=ok\n'
  printf 'scheduling_actions=resolve_date,update_availability,find_service,create_service,update_service\n'
  printf 'master_preferences_actions=get_master_preferences,save_master_name,save_master_style,save_default_work_hours\n'
  printf 'gateway_pid_before=%s\n' "$GATEWAY_PID_BEFORE"
  printf 'gateway_pid_after=%s\n' "$GATEWAY_PID_AFTER"
  printf 'gateway_state=active\n'
  printf 'gateway_error_scan=clean\n'
  printf 'calendar_data_changed_by_deployment=false\n'
  printf 'service_data_changed_by_deployment=false\n'
  printf 'master_preferences_data_changed_by_deployment=false\n'
  printf 'manual_sql_executed=false\n'
  printf 'rollback_performed=%s\n' "$ROLLBACK_PERFORMED"
}
