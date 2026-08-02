#!/usr/bin/env bash
# Candidate-only adapter for the normative deploy contract.
# It preserves deploy.sh on disk and constructs a guarded temporary copy that:
# - uses an isolated backend env for candidate API/WEB;
# - delegates the read-only client-forward snapshot;
# - suppresses client-forward stop/install/restore mutations;
# - preserves the already-running production client-forward service;
# - preserves the already-running production Compose client-bot container;
# - restores the pre-candidate legacy client-bot unit state after acceptance.

set -Eeuo pipefail
umask 077

die() {
  printf 'PRECONDITION_FAILED: %s\n' "$*" >&2
  exit 1
}

[[ -f "${BASH_SOURCE[0]}" ]] || die "candidate_deploy.sh must be executed from a regular file"
[[ $# -eq 1 ]] || die "usage: NAILS_CANDIDATE_ENV=/absolute/path candidate_deploy.sh <exact-sha>"

CANDIDATE_ENV="${NAILS_CANDIDATE_ENV:-}"
[[ -n "$CANDIDATE_ENV" ]] || die "NAILS_CANDIDATE_ENV is required"
[[ "$CANDIDATE_ENV" == /* ]] || die "NAILS_CANDIDATE_ENV must be an absolute path"
[[ "$CANDIDATE_ENV" != "/opt/nails/.env" ]] || die "candidate env must not be the production env"
[[ -f "$CANDIDATE_ENV" && ! -L "$CANDIDATE_ENV" ]] || die "candidate env must be a regular non-symlink file"

mode="$(stat -c '%a' "$CANDIDATE_ENV")"
(( (8#$mode & 8#077) == 0 )) || die "candidate env must not be accessible by group or others"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
DEPLOY_SCRIPT="${SCRIPT_DIR}/deploy.sh"
[[ -f "$DEPLOY_SCRIPT" ]] || die "normative deploy.sh is missing"

assignment='BACKEND_ENV="/opt/nails/.env"'
client_forward_invocation='bash "$WORKTREE/ops/client_forward/deploy_runtime.sh"'
client_forward_disabled_assertion='  systemctl is-active --quiet nails-client-forward.service && die "client forward is active while client runtime is disabled"'
client_bot_stop='compose stop nails-client-bot >/dev/null 2>&1 || true'
client_bot_up='compose up -d --no-deps --force-recreate --no-build nails-client-bot >/dev/null'
client_bot_remove='compose rm -sf nails-client-bot >/dev/null 2>&1 || true'

[[ "$(grep -Fxc "$assignment" "$DEPLOY_SCRIPT")" -eq 1 ]] || \
  die "deploy.sh BACKEND_ENV contract changed; adapter requires review"
client_forward_count="$(grep -Fc "$client_forward_invocation" "$DEPLOY_SCRIPT")"
[[ "$client_forward_count" -gt 0 ]] || \
  die "deploy.sh client-forward invocation contract changed; adapter requires review"
[[ "$(grep -Fxc "$client_forward_disabled_assertion" "$DEPLOY_SCRIPT")" -eq 1 ]] || \
  die "deploy.sh client-forward disabled assertion contract changed; adapter requires review"
client_bot_stop_count="$(grep -Fc "$client_bot_stop" "$DEPLOY_SCRIPT")"
client_bot_up_count="$(grep -Fc "$client_bot_up" "$DEPLOY_SCRIPT")"
client_bot_remove_count="$(grep -Fc "$client_bot_remove" "$DEPLOY_SCRIPT")"
client_bot_guard_count="$((client_bot_stop_count + client_bot_up_count + client_bot_remove_count))"
[[ "$client_bot_stop_count" -gt 0 && "$client_bot_up_count" -gt 0 && "$client_bot_remove_count" -gt 0 ]] || \
  die "deploy.sh client-bot runtime contract changed; adapter requires review"

production_client_bot_id_before="$(
  docker inspect -f '{{.Id}}' nails-nails-client-bot-1 2>/dev/null
)" || die "production Compose client-bot container is required"
[[ -n "$production_client_bot_id_before" ]] || die "production Compose client-bot container ID is empty"
[[ "$(docker inspect -f '{{.State.Running}}' nails-nails-client-bot-1)" == true ]] || \
  die "production Compose client-bot container must be running"

render_dir="${NAILS_CANDIDATE_RENDER_DIR:-}"
tmp_root="/opt/nails/tmp"
if [[ -n "$render_dir" ]]; then
  [[ "$render_dir" == /* ]] || die "NAILS_CANDIDATE_RENDER_DIR must be absolute"
  [[ -d "$render_dir" && ! -L "$render_dir" ]] || die "render dir must be a regular directory"
  tmp_root="${NAILS_CANDIDATE_TMP_ROOT:-$render_dir}"
  [[ "$tmp_root" == /* ]] || die "NAILS_CANDIDATE_TMP_ROOT must be absolute"
  [[ -d "$tmp_root" && ! -L "$tmp_root" ]] || die "candidate tmp root must be a regular directory"
elif [[ -n "${NAILS_CANDIDATE_TMP_ROOT:-}" ]]; then
  die "NAILS_CANDIDATE_TMP_ROOT is allowed only with render mode"
fi

install -d -m 700 "$tmp_root"
runtime_script="$(mktemp "$tmp_root/candidate-deploy.XXXXXX.sh")"
client_forward_guard="$(mktemp "$tmp_root/candidate-client-forward.XXXXXX.sh")"
legacy_unit_backup="$(mktemp "$tmp_root/candidate-client-bot-unit.XXXXXX")"
legacy_unit="/etc/systemd/system/nails-client-bot.service"
legacy_unit_existed="false"
legacy_enabled_before="$(systemctl is-enabled nails-client-bot.service 2>/dev/null || true)"
legacy_active_before="$(systemctl is-active nails-client-bot.service 2>/dev/null || true)"
legacy_restore_required="false"
if [[ -f "$legacy_unit" ]]; then
  cp -a "$legacy_unit" "$legacy_unit_backup"
  legacy_unit_existed="true"
fi

restore_legacy_client_bot_unit() {
  [[ "$legacy_restore_required" == "true" ]] || return 0
  systemctl disable --now nails-client-bot.service >/dev/null 2>&1 || true
  if [[ "$legacy_unit_existed" == "true" ]]; then
    cp -a "$legacy_unit_backup" "$legacy_unit"
  else
    rm -f "$legacy_unit"
  fi
  systemctl daemon-reload
  if [[ "$legacy_enabled_before" == "enabled" ]]; then
    systemctl enable nails-client-bot.service >/dev/null 2>&1
  fi
  if [[ "$legacy_active_before" == "active" ]]; then
    systemctl start nails-client-bot.service >/dev/null 2>&1
  fi
  printf 'production_legacy_client_bot_unit_restored=true\n'
}

cleanup() {
  local status=$?
  set +e
  restore_legacy_client_bot_unit
  rm -f -- "$runtime_script" "$client_forward_guard" "$legacy_unit_backup"
  return "$status"
}
trap cleanup EXIT

cat >"$client_forward_guard" <<'GUARD'
#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -ge 1 ]] || {
  printf 'PRECONDITION_FAILED: client-forward guard action is required\n' >&2
  exit 1
}

action="$1"
case "$action" in
  snapshot)
    [[ -n "${NAILS_DEPLOY_WORKTREE:-}" ]] || {
      printf 'PRECONDITION_FAILED: NAILS_DEPLOY_WORKTREE is required for snapshot\n' >&2
      exit 1
    }
    exec bash "${NAILS_DEPLOY_WORKTREE}/ops/client_forward/deploy_runtime.sh" "$@"
    ;;
  stop|install|restore)
    printf 'candidate_client_forward_%s_skipped=true\n' "$action"
    ;;
  *)
    printf 'PRECONDITION_FAILED: unsupported client-forward guard action: %s\n' "$action" >&2
    exit 1
    ;;
esac
GUARD
chmod 700 "$client_forward_guard"

awk \
  -v env_replacement='BACKEND_ENV="${NAILS_CANDIDATE_ENV:-/opt/nails/.env}"' \
  -v env_target="$assignment" \
  -v forward_replacement='bash "$NAILS_CANDIDATE_CLIENT_FORWARD_GUARD"' \
  -v forward_target="$client_forward_invocation" \
  -v assertion_replacement='  printf '\''candidate_client_forward_preserved=true\\n'\''' \
  -v assertion_target="$client_forward_disabled_assertion" \
  -v bot_stop="$client_bot_stop" \
  -v bot_up="$client_bot_up" \
  -v bot_remove="$client_bot_remove" \
  '{
    p = index($0, forward_target)
    trimmed = $0
    sub(/^[[:space:]]+/, "", trimmed)
    indent = substr($0, 1, length($0) - length(trimmed))
    if ($0 == env_target) {
      print env_replacement
    } else if (p > 0) {
      print substr($0, 1, p - 1) forward_replacement \
        substr($0, p + length(forward_target))
    } else if ($0 == assertion_target) {
      print assertion_replacement
    } else if (trimmed == bot_stop) {
      print indent "printf '\''candidate_client_bot_stop_preserved=true\\n'\''"
    } else if (trimmed == bot_up) {
      print indent "printf '\''candidate_client_bot_recreate_preserved=true\\n'\''"
    } else if (trimmed == bot_remove) {
      print indent "printf '\''candidate_client_bot_remove_preserved=true\\n'\''"
    } else {
      print
    }
  }' \
  "$DEPLOY_SCRIPT" >"$runtime_script"
chmod 700 "$runtime_script"

[[ "$(grep -Fxc 'BACKEND_ENV="${NAILS_CANDIDATE_ENV:-/opt/nails/.env}"' "$runtime_script")" -eq 1 ]] || \
  die "failed to construct isolated candidate deploy script"
[[ "$(grep -Fc 'bash "$NAILS_CANDIDATE_CLIENT_FORWARD_GUARD"' "$runtime_script")" -eq "$client_forward_count" ]] || \
  die "failed to guard every client-forward invocation"
[[ "$(grep -Fxc "  printf 'candidate_client_forward_preserved=true\\n'" "$runtime_script")" -eq 1 ]] || \
  die "failed to preserve active production client-forward assertion"
[[ "$(grep -Fc "$client_forward_invocation" "$runtime_script")" -eq 0 ]] || \
  die "unguarded client-forward invocation remains"
[[ "$(grep -Fc "candidate_client_bot_stop_preserved=true" "$runtime_script")" -eq "$client_bot_stop_count" ]] || \
  die "failed to guard every client-bot stop"
[[ "$(grep -Fc "candidate_client_bot_recreate_preserved=true" "$runtime_script")" -eq "$client_bot_up_count" ]] || \
  die "failed to guard every client-bot recreate"
[[ "$(grep -Fc "candidate_client_bot_remove_preserved=true" "$runtime_script")" -eq "$client_bot_remove_count" ]] || \
  die "failed to guard every client-bot removal"
[[ "$(grep -Fc "$client_bot_stop" "$runtime_script")" -eq 0 ]] || die "unguarded client-bot stop remains"
[[ "$(grep -Fc "$client_bot_up" "$runtime_script")" -eq 0 ]] || die "unguarded client-bot recreate remains"
[[ "$(grep -Fc "$client_bot_remove" "$runtime_script")" -eq 0 ]] || die "unguarded client-bot removal remains"

if [[ -n "$render_dir" ]]; then
  install -m 700 "$runtime_script" "$render_dir/runtime.sh"
  install -m 700 "$client_forward_guard" "$render_dir/client-forward-guard.sh"
  printf 'candidate_render_only=true\n'
  printf 'candidate_render_forward_count=%s\n' "$client_forward_count"
  printf 'candidate_render_client_bot_guard_count=%s\n' "$client_bot_guard_count"
  exit 0
fi

printf 'candidate_env_isolated=true\n'
printf 'production_env_unchanged=true\n'
printf 'production_client_forward_guarded=true\n'
printf 'production_client_bot_guarded=true\n'
printf 'production_legacy_client_bot_unit_snapshotted=true\n'
legacy_restore_required="true"

set +e
NAILS_CANDIDATE_ENV="$CANDIDATE_ENV" \
NAILS_CANDIDATE_CLIENT_FORWARD_GUARD="$client_forward_guard" \
  bash "$runtime_script" "$1"
status=$?
set -e

production_client_bot_id_after="$(
  docker inspect -f '{{.Id}}' nails-nails-client-bot-1 2>/dev/null
)" || die "production Compose client-bot container disappeared during candidate deploy"
[[ "$production_client_bot_id_after" == "$production_client_bot_id_before" ]] || \
  die "production Compose client-bot container ID changed during candidate deploy"
[[ "$(docker inspect -f '{{.State.Running}}' nails-nails-client-bot-1)" == true ]] || \
  die "production Compose client-bot container stopped during candidate deploy"
printf 'production_client_bot_preserved=true\n'
printf 'production_client_bot_container_id_unchanged=true\n'

exit "$status"
