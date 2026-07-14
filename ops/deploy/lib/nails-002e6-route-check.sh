#!/usr/bin/env bash

# Production intentionally disables the public OpenAPI endpoint. Verify the
# actual FastAPI route table inside the running API container instead.
verify_openapi() {
  compose exec -T nails-api python - <<'PY'
from app.main import app

routes: dict[str, set[str]] = {}
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
