# NAILS-002E6 — private route verification

Date: **2026-07-14**.

## Production result

The next E6 attempt passed the missing-image recovery stage:

```text
pre_api_image_object_exists=false
rollback_image_source=exported-running-container
rollback_image_config=sanitized
rollback_image_smoke=ok
```

The new API container was then created and started, but the runbook failed while requesting:

```text
GET /openapi.json
```

The API returned `404`, and the built-in rollback restored the previous healthy production state.

## Root cause

The production FastAPI application deliberately disables public documentation and schema endpoints:

```python
docs_url=None
redoc_url=None
openapi_url=None
```

The deployment runbook incorrectly depended on a public `/openapi.json` endpoint to verify routes. The application configuration was correct; the runbook check was not.

## Fix

The release now overrides the old route check with a small helper that runs inside the `nails-api` container.

It:

1. imports the actual `FastAPI` application;
2. reads the registered `app.routes` table;
3. verifies all required scheduling and master-preference routes and HTTP methods;
4. verifies that `app.openapi_url` is still disabled;
5. performs no request to `/openapi.json` and does not enable public documentation.

The existing compatibility marker remains:

```text
OPENAPI_ROUTES_OK=true
```

The final deployment report continues to use the established `openapi_*` markers, but they now mean that the internal application route table was verified.

## Production status

E6 remains not deployed until this change passes review and CI, is merged, and a new exact release SHA is deployed successfully.
