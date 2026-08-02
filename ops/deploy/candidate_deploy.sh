#!/usr/bin/env bash
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
forward_call='bash "$WORKTREE/ops/client_forward/deploy_runtime.sh"'
forward_assert='  systemctl is-active --quiet nails-client-forward.service && die "client forward is active while client runtime is disabled"'

[[ "$(grep -Fxc "$assignment" "$DEPLOY_SCRIPT")" -eq 1 ]] || die "deploy.sh BACKEND_ENV contract changed; adapter requires review"
forward_count="$(grep -Fc "$forward_call" "$DEPLOY_SCRIPT")"
[[ "$forward_count" -gt 0 ]] || die "deploy.sh client-forward invocation contract changed; adapter requires review"
[[ "$(grep -Fxc "$forward_assert" "$DEPLOY_SCRIPT")" -eq 1 ]] || die "deploy.sh client-forward disabled assertion contract changed; adapter requires review"

bot_stop_count="$(awk 'index($0, "compose stop ") && index($0, "nails-client-bot") { count++ } END { print count + 0 }' "$DEPLOY_SCRIPT")"
bot_up_count="$(awk 'index($0, "compose up ") && index($0, "--force-recreate") && index($0, "nails-client-bot") { count++ } END { print count + 0 }' "$DEPLOY_SCRIPT")"
bot_remove_count="$(awk 'index($0, "compose rm ") && index($0, "nails-client-bot") { count++ } END { print count + 0 }' "$DEPLOY_SCRIPT")"
[[ "$bot_stop_count" -gt 0 && "$bot_up_count" -gt 0 && "$bot_remove_count" -gt 0 ]] || die "deploy.sh client-bot runtime contract changed; adapter requires review"
bot_guard_count="$((bot_stop_count + bot_up_count + bot_remove_count))"

production_bot_id_before="$(docker inspect -f '{{.Id}}' nails-nails-client-bot-1 2>/dev/null)" || die "production Compose client-bot container is required"
[[ -n "$production_bot_id_before" ]] || die "production Compose client-bot container ID is empty"
[[ "$(docker inspect -f '{{.State.Running}}' nails-nails-client-bot-1)" == true ]] || die "production Compose client-bot container must be running"

render_dir="${NAILS_CANDIDATE_RENDER_DIR:-}"
tmp_root="/opt/nails/tmp"
if [[ -n "$render_dir" ]]; then
  [[ "$render_dir" == /* && -d "$render_dir" && ! -L "$render_dir" ]] || die "render dir must be an absolute regular directory"
  tmp_root="${NAILS_CANDIDATE_TMP_ROOT:-$render_dir}"
  [[ "$tmp_root" == /* && -d "$tmp_root" && ! -L "$tmp_root" ]] || die "candidate tmp root must be an absolute regular directory"
elif [[ -n "${NAILS_CANDIDATE_TMP_ROOT:-}" ]]; then
  die "NAILS_CANDIDATE_TMP_ROOT is allowed only with render mode"
fi

install -d -m 700 "$tmp_root"
runtime_script="$(mktemp "$tmp_root/candidate-deploy.XXXXXX.sh")"
forward_guard="$(mktemp "$tmp_root/candidate-client-forward.XXXXXX.sh")"
legacy_unit_backup="$(mktemp "$tmp_root/candidate-client-bot-unit.XXXXXX")"
legacy_unit=/etc/systemd/system/nails-client-bot.service
legacy_existed=false
legacy_enabled="$(systemctl is-enabled nails-client-bot.service 2>/dev/null || true)"
legacy_active="$(systemctl is-active nails-client-bot.service 2>/dev/null || true)"
legacy_restore=false
if [[ -f "$legacy_unit" ]]; then
  cp -a "$legacy_unit" "$legacy_unit_backup"
  legacy_existed=true
fi

restore_legacy_client_bot_unit() {
  [[ "$legacy_restore" == true ]] || return 0
  systemctl disable --now nails-client-bot.service >/dev/null 2>&1 || true
  if [[ "$legacy_existed" == true ]]; then
    cp -a "$legacy_unit_backup" "$legacy_unit"
  else
    rm -f "$legacy_unit"
  fi
  systemctl daemon-reload
  [[ "$legacy_enabled" == enabled ]] && systemctl enable nails-client-bot.service >/dev/null 2>&1 || true
  [[ "$legacy_active" == active ]] && systemctl start nails-client-bot.service >/dev/null 2>&1 || true
  printf 'production_legacy_client_bot_unit_restored=true\n'
}

cleanup() {
  local status=$?
  set +e
  restore_legacy_client_bot_unit
  rm -f -- "$runtime_script" "$forward_guard" "$legacy_unit_backup"
  return "$status"
}
trap cleanup EXIT

cat >"$forward_guard" <<'GUARD'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -ge 1 ]] || { printf 'PRECONDITION_FAILED: client-forward guard action is required\n' >&2; exit 1; }
case "$1" in
  snapshot)
    [[ -n "${NAILS_DEPLOY_WORKTREE:-}" ]] || { printf 'PRECONDITION_FAILED: NAILS_DEPLOY_WORKTREE is required for snapshot\n' >&2; exit 1; }
    exec bash "${NAILS_DEPLOY_WORKTREE}/ops/client_forward/deploy_runtime.sh" "$@"
    ;;
  stop|install|restore) printf 'candidate_client_forward_%s_skipped=true\n' "$1" ;;
  *) printf 'PRECONDITION_FAILED: unsupported client-forward guard action: %s\n' "$1" >&2; exit 1 ;;
esac
GUARD
chmod 700 "$forward_guard"

awk \
  -v env_target="$assignment" \
  -v forward_target="$forward_call" \
  -v assertion_target="$forward_assert" '
  {
    p = index($0, forward_target)
    trimmed = $0
    sub(/^[[:space:]]+/, "", trimmed)
    indent = substr($0, 1, length($0) - length(trimmed))
    if ($0 == env_target) {
      print "BACKEND_ENV=\"${NAILS_CANDIDATE_ENV:-/opt/nails/.env}\""
    } else if (p > 0) {
      print substr($0, 1, p - 1) "bash \"$NAILS_CANDIDATE_CLIENT_FORWARD_GUARD\"" substr($0, p + length(forward_target))
    } else if ($0 == assertion_target) {
      print "  printf '\''candidate_client_forward_preserved=true\\n'\''"
    } else if (index(trimmed, "compose stop ") && index(trimmed, "nails-client-bot")) {
      print indent ": # candidate preserves production client-bot stop"
    } else if (index(trimmed, "compose up ") && index(trimmed, "--force-recreate") && index(trimmed, "nails-client-bot")) {
      print indent ": # candidate preserves production client-bot recreate"
    } else if (index(trimmed, "compose rm ") && index(trimmed, "nails-client-bot")) {
      print indent ": # candidate preserves production client-bot removal"
    } else {
      print
    }
  }' "$DEPLOY_SCRIPT" >"$runtime_script"
chmod 700 "$runtime_script"

[[ "$(grep -Fxc 'BACKEND_ENV="${NAILS_CANDIDATE_ENV:-/opt/nails/.env}"' "$runtime_script")" -eq 1 ]] || die "failed to construct isolated candidate deploy script"
[[ "$(grep -Fc 'bash "$NAILS_CANDIDATE_CLIENT_FORWARD_GUARD"' "$runtime_script")" -eq "$forward_count" ]] || die "failed to guard every client-forward invocation"
[[ "$(grep -Fc "$forward_call" "$runtime_script")" -eq 0 ]] || die "unguarded client-forward invocation remains"
remaining_stop="$(awk 'index($0, "compose stop ") && index($0, "nails-client-bot") { count++ } END { print count + 0 }' "$runtime_script")"
remaining_up="$(awk 'index($0, "compose up ") && index($0, "--force-recreate") && index($0, "nails-client-bot") { count++ } END { print count + 0 }' "$runtime_script")"
remaining_remove="$(awk 'index($0, "compose rm ") && index($0, "nails-client-bot") { count++ } END { print count + 0 }' "$runtime_script")"
[[ "$remaining_stop" -eq 0 ]] || die "unguarded client-bot stop remains"
[[ "$remaining_up" -eq 0 ]] || die "unguarded client-bot recreate remains"
[[ "$remaining_remove" -eq 0 ]] || die "unguarded client-bot removal remains"
[[ "$(grep -Fc 'candidate preserves production client-bot stop' "$runtime_script")" -eq "$bot_stop_count" ]] || die "failed to guard every client-bot stop"
[[ "$(grep -Fc 'candidate preserves production client-bot recreate' "$runtime_script")" -eq "$bot_up_count" ]] || die "failed to guard every client-bot recreate"
[[ "$(grep -Fc 'candidate preserves production client-bot removal' "$runtime_script")" -eq "$bot_remove_count" ]] || die "failed to guard every client-bot removal"

if [[ -n "$render_dir" ]]; then
  install -m 700 "$runtime_script" "$render_dir/runtime.sh"
  install -m 700 "$forward_guard" "$render_dir/client-forward-guard.sh"
  printf 'candidate_render_only=true\n'
  printf 'candidate_render_forward_count=%s\n' "$forward_count"
  printf 'candidate_render_client_bot_guard_count=%s\n' "$bot_guard_count"
  exit 0
fi

printf 'candidate_env_isolated=true\n'
printf 'production_env_unchanged=true\n'
printf 'production_client_forward_guarded=true\n'
printf 'production_client_bot_guarded=true\n'
printf 'production_legacy_client_bot_unit_snapshotted=true\n'
legacy_restore=true

set +e
NAILS_CANDIDATE_ENV="$CANDIDATE_ENV" NAILS_CANDIDATE_CLIENT_FORWARD_GUARD="$forward_guard" bash "$runtime_script" "$1"
status=$?
set -e

production_bot_id_after="$(docker inspect -f '{{.Id}}' nails-nails-client-bot-1 2>/dev/null)" || die "production Compose client-bot container disappeared during candidate deploy"
[[ "$production_bot_id_after" == "$production_bot_id_before" ]] || die "production Compose client-bot container ID changed during candidate deploy"
[[ "$(docker inspect -f '{{.State.Running}}' nails-nails-client-bot-1)" == true ]] || die "production Compose client-bot container stopped during candidate deploy"
printf 'production_client_bot_preserved=true\n'
printf 'production_client_bot_container_id_unchanged=true\n'
exit "$status"
