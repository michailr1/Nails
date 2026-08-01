#!/usr/bin/env bash
# Candidate-only adapter for the normative deploy contract.
# It preserves deploy.sh byte-for-byte except for the single BACKEND_ENV assignment,
# allowing candidate API/WEB acceptance while production client runtime stays active.

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
[[ "$(grep -Fxc "$assignment" "$DEPLOY_SCRIPT")" -eq 1 ]] || \
  die "deploy.sh BACKEND_ENV contract changed; adapter requires review"

install -d -m 700 /opt/nails/tmp
runtime_script="$(mktemp /opt/nails/tmp/candidate-deploy.XXXXXX.sh)"
cleanup() {
  rm -f -- "$runtime_script"
}
trap cleanup EXIT

awk -v replacement='BACKEND_ENV="${NAILS_CANDIDATE_ENV:-/opt/nails/.env}"' \
  -v target="$assignment" \
  '{ if ($0 == target) print replacement; else print }' \
  "$DEPLOY_SCRIPT" >"$runtime_script"
chmod 700 "$runtime_script"

[[ "$(grep -Fxc 'BACKEND_ENV="${NAILS_CANDIDATE_ENV:-/opt/nails/.env}"' "$runtime_script")" -eq 1 ]] || \
  die "failed to construct isolated candidate deploy script"

printf 'candidate_env_isolated=true\n'
printf 'production_env_unchanged=true\n'

set +e
NAILS_CANDIDATE_ENV="$CANDIDATE_ENV" bash "$runtime_script" "$1"
status=$?
set -e
exit "$status"
