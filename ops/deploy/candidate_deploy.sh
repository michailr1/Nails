#!/usr/bin/env bash
# Candidate-only adapter for the normative deploy contract.
# It preserves deploy.sh on disk and constructs a guarded temporary copy that:
# - uses an isolated backend env for candidate API/WEB;
# - delegates the read-only client-forward snapshot;
# - suppresses client-forward stop/install/restore mutations;
# - preserves the already-running production client-forward service.

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

[[ "$(grep -Fxc "$assignment" "$DEPLOY_SCRIPT")" -eq 1 ]] || \
  die "deploy.sh BACKEND_ENV contract changed; adapter requires review"
[[ "$(grep -Fxc "$client_forward_invocation" "$DEPLOY_SCRIPT")" -eq 4 ]] || \
  die "deploy.sh client-forward invocation contract changed; adapter requires review"
[[ "$(grep -Fxc "$client_forward_disabled_assertion" "$DEPLOY_SCRIPT")" -eq 1 ]] || \
  die "deploy.sh client-forward disabled assertion contract changed; adapter requires review"

install -d -m 700 /opt/nails/tmp
runtime_script="$(mktemp /opt/nails/tmp/candidate-deploy.XXXXXX.sh)"
client_forward_guard="$(mktemp /opt/nails/tmp/candidate-client-forward.XXXXXX.sh)"
cleanup() {
  rm -f -- "$runtime_script" "$client_forward_guard"
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
  '{
    if ($0 == env_target) print env_replacement
    else if ($0 == forward_target) print forward_replacement
    else if ($0 == assertion_target) print assertion_replacement
    else print
  }' \
  "$DEPLOY_SCRIPT" >"$runtime_script"
chmod 700 "$runtime_script"

[[ "$(grep -Fxc 'BACKEND_ENV="${NAILS_CANDIDATE_ENV:-/opt/nails/.env}"' "$runtime_script")" -eq 1 ]] || \
  die "failed to construct isolated candidate deploy script"
[[ "$(grep -Fxc 'bash "$NAILS_CANDIDATE_CLIENT_FORWARD_GUARD"' "$runtime_script")" -eq 4 ]] || \
  die "failed to guard every client-forward invocation"
[[ "$(grep -Fxc "  printf 'candidate_client_forward_preserved=true\\n'" "$runtime_script")" -eq 1 ]] || \
  die "failed to preserve active production client-forward assertion"
[[ "$(grep -Fxc "$client_forward_invocation" "$runtime_script")" -eq 0 ]] || \
  die "unguarded client-forward invocation remains"

printf 'candidate_env_isolated=true\n'
printf 'production_env_unchanged=true\n'
printf 'production_client_forward_guarded=true\n'

set +e
NAILS_CANDIDATE_ENV="$CANDIDATE_ENV" \
NAILS_CANDIDATE_CLIENT_FORWARD_GUARD="$client_forward_guard" \
  bash "$runtime_script" "$1"
status=$?
set -e
exit "$status"
