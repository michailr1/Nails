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
source <(git show "${RELEASE_SHA}:ops/deploy/lib/nails-002e6-runtime.sh")
nails_002e6_main
