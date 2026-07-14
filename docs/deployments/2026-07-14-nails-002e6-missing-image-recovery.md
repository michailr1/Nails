# NAILS-002E6 — missing running-image object recovery

Date: **2026-07-14**.

## Second production attempt

The corrected E6 deployment still stopped safely before the release image build.

```text
DEPLOYMENT_FAILED=true
runbook=NAILS-002E6
failed_line=286
head_current=fbfd85748805795bf2e6d2df6c0ff85f42954447
ROLLBACK_PERFORMED=true
ROLLBACK_TARGET_HEAD=385a92962e3736553335d717adcdf4b83ac8a8b3
ROLLBACK_HEAD_CURRENT=385a92962e3736553335d717adcdf4b83ac8a8b3
ROLLBACK_API_HEALTH={"status":"ok"}
ROLLBACK_GATEWAY_STATE=active
```

Backups and the complete root-only log:

```text
database_backup=/opt/nails/backups/nails-before-002e6-20260714T074701Z.sql.gz
runtime_backup=/root/.hermes/profiles/nails/backups/nails-002e6-20260714T074701Z
full_log=/root/.hermes/profiles/nails/backups/nails-002e6-run-20260714T074701Z.log
```

Production returned to the original E4 state and remained healthy.

## Confirmed Docker state

Read-only diagnostics established:

```text
running container image ID:
sha256:4c6a5afc69fef83799f987a26ea88fdc1dd8f7c13703a6700e7809ba00b1f596

running container image reference:
nails-nails-api

running image object exists:
false

current nails-nails-api tag image ID:
sha256:d6a4badee7e3dd63fe80d0dbeb38c1651725003d010136e942a7d12b93a115e3
```

The container continued to run from its retained root filesystem, but Docker could no longer address its original image ID as an image object. The Compose tag had already moved to an image produced by the first failed attempt.

Therefore a direct command such as:

```text
docker image tag <running-container-image-id> <rollback-tag>
```

could not work after the first incident.

## Recovery design

The release entrypoint loads a narrowly scoped compatibility hook before executing the reviewed E6 runtime.

The hook intercepts only the exact operation that preserves the pre-deployment API image.

If the running image object still exists, behavior is unchanged: the exact image is tagged for rollback.

If the image object is missing, the hook:

1. exports the filesystem of the still-running, read-only API container;
2. imports it as the unique E6 rollback image;
3. reconstructs only the non-secret Docker metadata required by the Compose service;
4. explicitly sets the unprivileged `nails` user and `/app` working directory;
5. verifies image metadata contains no database URL, internal API key or PostgreSQL/application database credentials;
6. runs an offline, read-only Python import smoke test with dummy settings and no network;
7. replaces the runtime rollback image variable with the recovered, addressable image ID;
8. leaves the running API container, database container and gateway unchanged until the normal E6 cutover stage.

The recovery deliberately does **not** use `docker commit`, because committing a Compose container could copy runtime environment values, including secrets, into image metadata.

## Rollback behavior

After successful recovery, the inherited E6 rollback function receives the recovered image ID through `API_IMAGE_ID_BEFORE`. If any later deployment stage fails, it can retag that addressable image to the Compose image reference before recreating the API.

The original missing container image ID remains recorded in the runtime backup for incident auditability.

## Expected recovery markers

A production run on the current incident state should include:

```text
pre_api_image_object_exists=false
rollback_image_source=exported-running-container
rollback_image_config=sanitized
rollback_image_smoke=ok
rollback_capture_log=/root/.hermes/profiles/nails/backups/<run>/api-rollback-capture.log
```

The normal success requirements remain:

```text
NAILS_002E6_DEPLOYMENT_OK
rollback_image_preserved_during_build=true
rollback_performed=false
```

## Production status

E6 is still not deployed. Do not repeat production deployment until this recovery change is reviewed, all CI checks pass, the pull request is merged, and a new exact release SHA is selected.
