#!/usr/bin/env bash

# Compatibility recovery for the E6 production incident where the running
# container still references an image ID that Docker no longer exposes as an
# image object. This file is sourced after the normal E6 runtime and only
# intercepts its exact rollback-tag operation.

NAILS_E6_PRE_API_IMAGE_OBJECT_EXISTS=""
NAILS_E6_ROLLBACK_IMAGE_SOURCE=""
NAILS_E6_ROLLBACK_IMAGE_ID=""
NAILS_E6_ROLLBACK_IMAGE_CONFIG=""
NAILS_E6_ROLLBACK_IMAGE_SMOKE=""
NAILS_E6_ROLLBACK_CAPTURE_LOG=""

nails_002e6_remove_partial_recovery_image() {
  command docker image rm "$API_ROLLBACK_IMAGE_REF" >/dev/null 2>&1 || true
}

nails_002e6_capture_running_api_image() {
  local recovered_id image_env

  NAILS_E6_ROLLBACK_CAPTURE_LOG="${RUNTIME_BACKUP}/api-rollback-capture.log"

  if ! {
    command docker export "$API_CONTAINER_BEFORE" |
      command docker import \
        --change 'USER nails' \
        --change 'WORKDIR /app' \
        --change 'ENV PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
        --change 'ENV LANG=C.UTF-8' \
        --change 'ENV PYTHONDONTWRITEBYTECODE=1' \
        --change 'ENV PYTHONUNBUFFERED=1' \
        --change 'ENV PIP_DISABLE_PIP_VERSION_CHECK=1' \
        --change 'EXPOSE 8000' \
        --change 'CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]' \
        - "$API_ROLLBACK_IMAGE_REF"
  } >"$NAILS_E6_ROLLBACK_CAPTURE_LOG" 2>&1; then
    chmod 600 "$NAILS_E6_ROLLBACK_CAPTURE_LOG" 2>/dev/null || true
    nails_002e6_remove_partial_recovery_image
    fail "could not capture the running API filesystem for rollback"
    return 1
  fi
  chmod 600 "$NAILS_E6_ROLLBACK_CAPTURE_LOG"

  recovered_id="$(command docker image inspect -f '{{.Id}}' "$API_ROLLBACK_IMAGE_REF")"
  [[ -n "$recovered_id" ]] || {
    nails_002e6_remove_partial_recovery_image
    fail "captured rollback API image has no image ID"
    return 1
  }

  [[ "$(command docker image inspect -f '{{.Config.User}}' "$API_ROLLBACK_IMAGE_REF")" == "nails" ]] || {
    nails_002e6_remove_partial_recovery_image
    fail "captured rollback API image has an unsafe user"
    return 1
  }
  [[ "$(command docker image inspect -f '{{.Config.WorkingDir}}' "$API_ROLLBACK_IMAGE_REF")" == "/app" ]] || {
    nails_002e6_remove_partial_recovery_image
    fail "captured rollback API image has an unexpected working directory"
    return 1
  }

  image_env="$(command docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$API_ROLLBACK_IMAGE_REF")"
  if grep -Eq '^(DATABASE_URL|INTERNAL_API_KEY|NAILS_INTERNAL_API_KEY|POSTGRES_[A-Z_]+|APP_DB_[A-Z_]+)=' <<<"$image_env"; then
    nails_002e6_remove_partial_recovery_image
    fail "captured rollback API image contains runtime secrets in image metadata"
    return 1
  fi

  if ! command docker run --rm \
    --network none \
    --read-only \
    --tmpfs /tmp:size=16m,mode=1777 \
    --entrypoint python \
    -e 'DATABASE_URL=postgresql+psycopg://nails:nails@127.0.0.1/nails' \
    -e 'APP_TIMEZONE=Europe/Berlin' \
    -e 'INTERNAL_API_KEY=0000000000000000000000000000000000000000000000000000000000000000' \
    "$API_ROLLBACK_IMAGE_REF" \
    -c 'import app.main' >>"$NAILS_E6_ROLLBACK_CAPTURE_LOG" 2>&1; then
    nails_002e6_remove_partial_recovery_image
    fail "captured rollback API image failed an offline import smoke test"
    return 1
  fi

  NAILS_E6_PRE_API_IMAGE_OBJECT_EXISTS="false"
  NAILS_E6_ROLLBACK_IMAGE_SOURCE="exported-running-container"
  NAILS_E6_ROLLBACK_IMAGE_ID="$recovered_id"
  NAILS_E6_ROLLBACK_IMAGE_CONFIG="sanitized"
  NAILS_E6_ROLLBACK_IMAGE_SMOKE="ok"

  # The normal E6 runtime and its inherited rollback function use this
  # variable. Point it at the recovered image object so all later checks and
  # rollback retagging operate on an image Docker can actually address.
  API_IMAGE_ID_BEFORE="$recovered_id"
  IMAGE_BUILT="true"
}

# Delegate every Docker call except the exact E6 operation that preserves the
# pre-deployment API image under the unique rollback tag.
docker() {
  local rc

  if [[ "$#" -eq 4 \
    && "$1" == "image" \
    && "$2" == "tag" \
    && "$3" == "$API_IMAGE_ID_BEFORE" \
    && "$4" == "$API_ROLLBACK_IMAGE_REF" ]]; then

    if command docker image inspect "$API_IMAGE_ID_BEFORE" >/dev/null 2>&1; then
      NAILS_E6_PRE_API_IMAGE_OBJECT_EXISTS="true"
      NAILS_E6_ROLLBACK_IMAGE_SOURCE="existing-image"
      NAILS_E6_ROLLBACK_IMAGE_ID="$API_IMAGE_ID_BEFORE"
      NAILS_E6_ROLLBACK_IMAGE_CONFIG="original"
      NAILS_E6_ROLLBACK_IMAGE_SMOKE="not-required"
      command docker "$@"
      rc=$?
    else
      nails_002e6_capture_running_api_image || return $?
      command docker image tag "$API_IMAGE_ID_BEFORE" "$API_ROLLBACK_IMAGE_REF"
      rc=$?
    fi

    if (( rc == 0 )); then
      [[ "$(command docker image inspect -f '{{.Id}}' "$API_ROLLBACK_IMAGE_REF")" == "$API_IMAGE_ID_BEFORE" ]] || return 1
      printf 'pre_api_image_object_exists=%s\n' "$NAILS_E6_PRE_API_IMAGE_OBJECT_EXISTS"
      printf 'rollback_image_source=%s\n' "$NAILS_E6_ROLLBACK_IMAGE_SOURCE"
      printf 'rollback_image_id=%s\n' "$NAILS_E6_ROLLBACK_IMAGE_ID"
      printf 'rollback_image_config=%s\n' "$NAILS_E6_ROLLBACK_IMAGE_CONFIG"
      printf 'rollback_image_smoke=%s\n' "$NAILS_E6_ROLLBACK_IMAGE_SMOKE"
      if [[ -n "$NAILS_E6_ROLLBACK_CAPTURE_LOG" ]]; then
        printf 'rollback_capture_log=%s\n' "$NAILS_E6_ROLLBACK_CAPTURE_LOG"
      fi
    fi
    return "$rc"
  fi

  command docker "$@"
}
