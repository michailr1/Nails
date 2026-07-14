# NAILS-002E6 — fresh API image build

Date: **2026-07-14**.

## Production result

The latest E6 attempt successfully preserved the old image and recreated `nails-api`, but the internal route check failed:

```text
AssertionError: /api/v1/scheduling/date/resolve
```

The built-in rollback restored:

```text
HEAD=385a92962e3736553335d717adcdf4b83ac8a8b3
backend health=ok
gateway=active
```

## What the repository contains

The reviewed release source does contain the expected runtime contract:

- scheduling router prefix: `/api/v1/scheduling`;
- route: `POST /date/resolve`;
- scheduling router included in the FastAPI application.

Therefore the route expectation is not obsolete. The route check detected that the newly selected Docker image did not contain the reviewed release application.

## Simple correction

The E6 runbook now handles only its existing `compose build nails-api` call differently:

1. build explicitly from `/opt/nails/repo/backend`;
2. use `/opt/nails/repo/backend/Dockerfile`;
3. disable layer reuse for this recovery deployment with `--no-cache`;
4. tag the result with the existing Compose API image reference;
5. verify the complete route table in that image before stopping the gateway;
6. after recreation, verify the same route table in the running container.

All other Compose commands continue through the normal production Compose file and `/opt/nails/.env`.

This change does not alter backend routes, database schema, plugins, skills, gateway configuration or business data.

## Safety effect

A stale or incorrectly built image now fails while the old API and gateway are still running. The deployment does not enter the cutover stage unless the built image contains the reviewed routes.

## Production status

E6 remains not deployed until this correction passes review and CI, is merged, and a new exact release SHA is deployed successfully.
