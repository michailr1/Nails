# NAILS-002E6 — image lookup failure and rollback

Date: **2026-07-14**.

## Result

The first E6 production attempt did not deploy the release.

Observed markers:

```text
DEPLOYMENT_FAILED=true
failed_line=285
head_current=385a92962e3736553335d717adcdf4b83ac8a8b3
ROLLBACK_PERFORMED=true
ROLLBACK_HEAD_CURRENT=385a92962e3736553335d717adcdf4b83ac8a8b3
ROLLBACK_API_HEALTH={"status":"ok"}
ROLLBACK_GATEWAY_STATE=active
```

Backups were created before failure:

```text
database_backup=/opt/nails/backups/nails-before-002e6-20260714T070453Z.sql.gz
runtime_backup=/root/.hermes/profiles/nails/backups/nails-002e6-20260714T070453Z
```

Production remained on the pre-E6 repository/runtime state.

## Root cause

The runbook built a replacement image using the same Compose image reference as the running API container, then called:

```text
compose images -q nails-api
```

Docker had already moved the tag to the newly built image and removed the old image metadata from the image store. The old container could continue running, but Compose attempted to inspect its former image ID and failed with:

```text
No such image: sha256:4c6a5afc69fef83799f987a26ea88fdc1dd8f7c13703a6700e7809ba00b1f596
```

This also exposed a rollback weakness: after API recreation, the old image ID could have become unavailable unless it was explicitly retained under a separate tag before the build.

## Fix

The corrected E6 runbook:

1. tags the current API image with a unique rollback reference before building;
2. verifies that rollback reference resolves to the exact pre-deployment image ID;
3. captures build output in a root-only runtime backup log;
4. resolves the new image ID directly from the Compose image reference with `docker image inspect`;
5. never uses `compose images -q` after retagging;
6. verifies the recreated API container uses the exact new image ID;
7. removes the temporary rollback tag only after all final checks succeed;
8. uses quiet Git and Compose output so routine build/download logs are not pasted into the working chat.

## Production status

E6 remains not deployed until a corrected merged release reaches:

```text
NAILS_002E6_DEPLOYMENT_OK
rollback_performed=false
```
