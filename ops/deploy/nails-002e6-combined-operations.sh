#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO="/opt/nails/repo"
RELEASE_SHA="${NAILS_RELEASE_SHA:-}"

if [[ ! "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: NAILS_RELEASE_SHA must be an exact 40-character commit SHA" >&2
  exit 1
fi

cd "$REPO"
git cat-file -e "${RELEASE_SHA}:ops/deploy/lib/nails-002e6-runtime.sh"
git cat-file -e "${RELEASE_SHA}:ops/deploy/lib/nails-002e6-image-recovery.sh"
git cat-file -e "${RELEASE_SHA}:ops/deploy/lib/nails-002e6-route-check.sh"
source <(git show "${RELEASE_SHA}:ops/deploy/lib/nails-002e6-runtime.sh")
source <(git show "${RELEASE_SHA}:ops/deploy/lib/nails-002e6-image-recovery.sh")
source <(git show "${RELEASE_SHA}:ops/deploy/lib/nails-002e6-route-check.sh")
declare -F nails_002e6_main >/dev/null
declare -F nails_002e6_capture_running_api_image >/dev/null
declare -F verify_openapi >/dev/null
declare -F docker >/dev/null
nails_002e6_main
