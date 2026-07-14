#!/usr/bin/env bash

build_fresh_api_image() {
  command docker build \
    --no-cache \
    --file "$REPO/backend/Dockerfile" \
    --tag "$API_IMAGE_REF_BEFORE" \
    "$REPO/backend"

  verify_built_api_image "$API_IMAGE_REF_BEFORE"
}

# The E6 runtime already calls `compose build nails-api`. Keep that call site
# simple, but make this one build explicit and fresh. All other compose calls
# use the normal production compose file and environment.
compose() {
  if [[ "$#" -eq 2 && "$1" == "build" && "$2" == "nails-api" ]]; then
    build_fresh_api_image
    return
  fi

  command docker compose --env-file "$BACKEND_ENV" "$@"
}
