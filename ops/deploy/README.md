# Production deployment runbooks

These scripts are authored, reviewed and merged by the main ChatGPT agent. The VPS agent never writes or edits them and never substitutes its own commands.

Before any production runbook, read:

- [`../../AGENTS.md`](../../AGENTS.md);
- [`../../docs/context/current.md`](../../docs/context/current.md);
- [`../../docs/operations/agent-responsibilities.md`](../../docs/operations/agent-responsibilities.md);
- [`../../docs/operations/production-infrastructure.md`](../../docs/operations/production-infrastructure.md);
- [`../../docs/operations/hermes-plugin-runtime.md`](../../docs/operations/hermes-plugin-runtime.md).

## Execution contract

A runbook is executed only from an exact merged release SHA approved by the main agent. The VPS agent reads the script from the fetched Git object without editing or creating a local copy.

Generic execution shape:

```bash
bash -lc '
set -Eeuo pipefail
cd /opt/nails/repo
git fetch origin main
export NAILS_RELEASE_SHA="<EXACT_APPROVED_RELEASE_SHA>"
git show "${NAILS_RELEASE_SHA}:ops/deploy/<APPROVED_RUNBOOK>.sh" | bash
'
```

The main agent replaces both placeholders. The VPS agent must not resolve them itself.

## NAILS-002E5 — current deployment candidate

Entrypoint:

```text
ops/deploy/nails-002e5-date-availability.sh
```

Libraries loaded from the same exact release commit:

```text
ops/deploy/lib/nails-002e5-common.sh
ops/deploy/lib/nails-002e5-runtime.sh
```

Purpose:

- deploy the trusted backend date resolver;
- deploy direct confirmed availability editing;
- update `nails-scheduling` from `0.1.0` to `0.2.0`;
- update both onboarding and scheduling skills;
- keep the existing Hermes config and least-privilege Telegram boundary.

Expected production baseline:

```text
385a92962e3736553335d717adcdf4b83ac8a8b3
Alembic 0006
nails-onboarding 0.5.0
nails-scheduling 0.1.0
```

Reviewed code ancestor:

```text
c9e400c80398bd4367aad0ed0416ee0fc6a79b2d
```

The runbook:

1. verifies hostname, branch, clean tree, exact baseline and exact approved release SHA;
2. verifies no Alembic files changed and confirms revision `0006`;
3. verifies root user-level systemd, Hermes version, plugin list `0.1.0`, structured YAML and matching internal keys;
4. verifies current repository sources exactly match installed runtime files;
5. creates a root-only PostgreSQL dump and runtime backup;
6. fast-forwards to the exact approved release;
7. builds the new API image while the old API remains online;
8. stops only the root user-level Nails gateway;
9. recreates only `nails-api` with `--no-deps`;
10. proves `nails-db` and the Docker daemon remain unchanged;
11. verifies Alembic remains `0006` and the new OpenAPI routes exist;
12. installs exact scheduling plugin `0.2.0` files and both skills;
13. proves `/root/.hermes/profiles/nails/config.yaml` did not change;
14. verifies plugin list, registry, Telegram visibility and the new `resolve_date` / `update_availability` actions;
15. starts only the root user-level gateway and scans its journal;
16. restores repository, old API image/runtime/config and gateway after any post-mutation failure.

The API container is expected to change. The database container and Docker daemon must not change.

The container command can safely execute `alembic upgrade head`, but the release contains no migration-file changes and both before/after revision must remain `0006`. Therefore the contract is:

```text
schema_revision_changed=false
```

The runbook does not correct the mistaken July dates. It performs no ad-hoc SQL and never calls `nails_scheduling`:

```text
calendar_data_changed_by_deployment=false
manual_sql_executed=false
```

After successful infrastructure deployment, the user corrects the calendar through the real Telegram confirmation flow. This proves the same experience intended for daily use.

Success marker:

```text
NAILS_002E5_DEPLOYMENT_OK
```

E5 is not authorized merely because the files exist on a branch. It may run only after PR review, green CI, merge to `main`, and issuance of an exact release SHA by the main agent.

## NAILS-002E4 V3 — successful historical deployment

Successful runbook:

```text
ops/deploy/nails-002e4-v3.sh
```

Success marker reached in production:

```text
NAILS_002E4_V3_DEPLOYMENT_OK
```

V3 installed both Nails plugins, preserved backend/Docker and established the correct root user-level systemd and plugin verification boundaries. Its verification used `discover_plugins()` and never with `force=True`; Telegram toolsets were compared by exact membership, not iteration order. It remains an audit record and must not be rerun for E5.

## NAILS-002E4 V2 — blocked after verified rollback

`ops/deploy/nails-002e4-v2.sh` must **not** be executed again.

V2 atomically updates structured YAML and historically appended `nails-scheduling` to `plugins.enabled` and `nails_scheduling` to `platform_toolsets.telegram`, but its final read-only assertion was defective. The unused success marker was:

```text
NAILS_002E4_DEPLOYMENT_OK
```

It incorrectly compared unordered Telegram toolsets by list order and called `discover_plugins(force=True)`. Its predefined rollback restored the old repository/runtime/config and returned the gateway to active:

```text
ROLLBACK_GATEWAY_STATE=active
```

This runbook is not authorized merely because it exists on a branch.

## NAILS-002E4 V1 — blocked legacy runbook

`ops/deploy/nails-002e4.sh` must **not** be executed again.

It assumed system-level systemd and a fabricated comma-separated allowlist. The real gateway uses root user-level systemd, and the authoritative config is structured YAML:

```text
/root/.hermes/profiles/nails/config.yaml
```

Correct gateway boundary:

```bash
XDG_RUNTIME_DIR=/run/user/0 systemctl --user \
  <status|show|stop|start|restart> hermes-gateway-nails.service
```

Old runbooks remain in Git only for auditability. Their presence never authorizes execution.
