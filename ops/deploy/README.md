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

## NAILS-002E6 — active combined deployment candidate

Entrypoint:

```text
ops/deploy/nails-002e6-combined-operations.sh
```

Runtime:

```text
ops/deploy/lib/nails-002e6-runtime.sh
```

E6 reuses the reviewed shared backup and rollback functions in:

```text
ops/deploy/lib/nails-002e5-common.sh
```

Purpose:

- deploy exact date resolution;
- deploy confirmed availability editing;
- deploy service creation, editing, archive and restore;
- update `nails-scheduling` directly to `0.3.0`;
- update onboarding and scheduling skills;
- keep structured Hermes config and least-privilege Telegram visibility unchanged.

Allowed starting states:

```text
385a92962e3736553335d717adcdf4b83ac8a8b3 + nails-scheduling 0.1.0
a0ef8c5c26301a9f6950544afd0e070b7e691582 + nails-scheduling 0.2.0
```

Any other repository HEAD or plugin version stops before mutation.

Reviewed combined code ancestor:

```text
e4443a736c5a0d5a34239a5257b7764592834e5b
```

The runbook:

1. validates hostname, branch, clean tree, one exact allowed baseline and the approved release SHA;
2. verifies root user-level systemd, Hermes version, structured YAML and matching internal keys;
3. verifies current source/runtime equality before mutation;
4. rejects Alembic file changes and confirms revision `0006`;
5. creates a root-only PostgreSQL dump and runtime/config/skill/image backup;
6. fast-forwards to the exact release;
7. builds the new API image while the old API remains online;
8. stops only the root user-level Nails gateway;
9. recreates only `nails-api` with `--no-deps`;
10. proves `nails-db` and Docker daemon remain unchanged;
11. verifies date, availability and service-management OpenAPI routes;
12. installs scheduling plugin `0.3.0` and both skills;
13. proves `/root/.hermes/profiles/nails/config.yaml` did not change;
14. verifies plugin list, registry, Telegram visibility and the complete action set;
15. starts only the root user-level gateway and scans its journal;
16. restores the detected starting repository, API image/runtime/config/skills and gateway after any post-mutation failure.

Expected isolation markers:

```text
schema_revision_changed=false
db_container_unchanged=true
docker_daemon_unchanged=true
calendar_data_changed_by_deployment=false
service_data_changed_by_deployment=false
manual_sql_executed=false
```

Deployment never invokes `nails_scheduling` or `nails_onboarding`. Calendar and service corrections are made afterward through real confirmed Telegram flows.

Success marker:

```text
NAILS_002E6_DEPLOYMENT_OK
```

E6 is not authorized merely because its files exist on a branch. It may run only after PR review, green CI, merge to `main`, and issuance of an exact release SHA by the main agent.

## NAILS-002E5 — superseded candidate

Historical entrypoint:

```text
ops/deploy/nails-002e5-date-availability.sh
```

Historical success marker:

```text
NAILS_002E5_DEPLOYMENT_OK
```

E5 was designed for the date and availability fix only. Because E6 safely supports both pre-E5 `0.1.0` and post-E5 `0.2.0` baselines, E5 must not be issued as the active deployment command.

Its preserved contract includes:

```text
calendar_data_changed_by_deployment=false
manual_sql_executed=false
```

## NAILS-002E4 V3 — successful historical deployment

Successful runbook:

```text
ops/deploy/nails-002e4-v3.sh
```

Success marker reached in production:

```text
NAILS_002E4_V3_DEPLOYMENT_OK
```

V3 installed both Nails plugins, preserved backend/Docker and established the correct root user-level systemd and plugin verification boundaries. Its verification used `discover_plugins()` and never with `force=True`; Telegram toolsets were compared by exact membership, not iteration order.

## NAILS-002E4 V2 — permanently unavailable

`ops/deploy/nails-002e4-v2.sh` must **not** be executed again.

V2 atomically updates structured YAML and historically appended `nails-scheduling` to `plugins.enabled` and `nails_scheduling` to `platform_toolsets.telegram`, but its final read-only assertion was defective. The unused marker was:

```text
NAILS_002E4_DEPLOYMENT_OK
```

It compared unordered toolsets by list order and called `discover_plugins(force=True)`. Rollback restored repository/runtime/config and returned the gateway to active:

```text
ROLLBACK_GATEWAY_STATE=active
```

This runbook is not authorized merely because it exists on a branch.

## NAILS-002E4 V1 — permanently unavailable

`ops/deploy/nails-002e4.sh` must **not** be executed again.

It assumed system-level systemd and a fabricated comma-separated allowlist. The authoritative config is:

```text
/root/.hermes/profiles/nails/config.yaml
```

Correct gateway boundary:

```bash
XDG_RUNTIME_DIR=/run/user/0 systemctl --user \
  <status|show|stop|start|restart> hermes-gateway-nails.service
```

Old runbooks remain in Git only for auditability. Their presence never authorizes execution.
