#!/usr/bin/env bash

verify_api_routes() {
  "$@" python - <<'PY'
from app.main import app

routes = {}
for route in app.routes:
    path = getattr(route, "path", None)
    methods = getattr(route, "methods", None) or set()
    if path:
        routes.setdefault(path, set()).update(method.lower() for method in methods)

expected = {
    "/api/v1/scheduling/date/resolve": {"post"},
    "/api/v1/scheduling/availability": {"put"},
    "/api/v1/scheduling/services": {"get", "post", "put"},
    "/api/v1/scheduling/services/exact": {"get"},
    "/api/v1/scheduling/day": {"get"},
    "/api/v1/scheduling/slots": {"get"},
    "/api/v1/onboarding/preferences": {"get"},
    "/api/v1/onboarding/preferences/name": {"put"},
    "/api/v1/onboarding/preferences/style": {"put"},
    "/api/v1/onboarding/preferences/default-work-hours": {"put"},
}

assert app.openapi_url is None
assert "/openapi.json" not in routes
for path, methods in expected.items():
    assert path in routes, path
    assert methods.issubset(routes[path]), (path, sorted(routes[path]))

print("OPENAPI_ROUTES_OK=true")
PY
}

verify_built_api_image() {
  local image="$1"
  verify_api_routes \
    docker run --rm \
    --network none \
    --read-only \
    --tmpfs /tmp:size=16m,mode=1777 \
    "$image"
}

# Kept under the old function name because the E6 runtime already calls it.
verify_openapi() {
  verify_api_routes compose exec -T nails-api
}
