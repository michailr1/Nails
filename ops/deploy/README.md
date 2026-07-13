# Production deployment runbooks

These scripts are authored, reviewed, and merged by the main ChatGPT agent. The VPS agent never writes or edits them and never substitutes its own commands.

Before preparing or executing any production runbook, read:

- [`../../AGENTS.md`](../../AGENTS.md);
- [`../../docs/operations/agent-responsibilities.md`](../../docs/operations/agent-responsibilities.md);
- [`../../docs/operations/production-infrastructure.md`](../../docs/operations/production-infrastructure.md);
- [`../../docs/operations/hermes-plugin-runtime.md`](../../docs/operations/hermes-plugin-runtime.md).

The production infrastructure and Hermes plugin runtime documents are the sources of truth for the service manager, runtime paths, profile configuration, plugin keys, and tool visibility. Runbooks must not reconstruct those facts from chat memory.

## Execution contract

A production runbook is executed only from an exact release commit approved by the main agent. The production checkout may still be on the previous release, so the VPS agent reads the script directly from the fetched Git object and pipes it to Bash without creating or editing a local copy.

The main agent supplies the final 40-character `NAILS_RELEASE_SHA` after merge. The generic execution shape is:

```bash
bash -lc '
set -Eeuo pipefail
cd /opt/nails/repo
git fetch origin main
export NAILS_RELEASE_SHA="<EXACT_APPROVED_RELEASE_SHA>"
git show "${NAILS_RELEASE_SHA}:ops/deploy/<APPROVED_RUNBOOK>.sh" | bash
'
```

The placeholders are never resolved by the VPS agent. They are replaced by the main agent in the exact deployment prompt.

## NAILS-002E4 V3 — current candidate

The only E4 runbook eligible for approval after merge is:

```text
ops/deploy/nails-002e4-v3.sh
```

V3 preserves the verified V2 safety boundary and corrects the verification defect found during the rolled-back production attempt:

- Hermes plugin discovery is called idempotently with `discover_plugins()` and never with `force=True`;
- `_get_platform_tools(config, "telegram")` is treated as an unordered set-like collection;
- Telegram toolsets are compared by exact membership, not iteration order;
- diagnostic assertions include observed values instead of returning an unexplained bare assertion.

The runbook still:

- requires production baseline `5565a524b75a04fe5d8bc2c3e758d2994e9d9c12`;
- requires the approved release to contain the reviewed scheduling implementation and the V2 rollback evidence;
- verifies Hermes Agent `v0.18.2 (2026.7.7.2)` and the exact import path;
- verifies root user-level systemd, the exact unit fragment, process command, parent manager, PID, restart policy, and active state;
- verifies onboarding is the only enabled Nails plugin before mutation;
- verifies the exact semantic YAML pre-state;
- creates a root-only backup before any production mutation;
- fast-forwards to the exact approved release SHA;
- installs only the reviewed scheduling plugin files and scheduling skill;
- appends `nails-scheduling` to `plugins.enabled` without replacing `nails-onboarding`;
- explicitly appends `nails_scheduling` to `platform_toolsets.telegram`;
- atomically updates and re-parses `/root/.hermes/profiles/nails/config.yaml`;
- verifies config, plugin list, registry, toolsets, Telegram definitions, logs, and matching internal keys;
- stops and starts only the root user-level Nails gateway;
- proves `nails-api`, `nails-db`, and the Docker daemon were not restarted or replaced;
- performs no migration, SQL, backend deployment, backend restart, or plugin tool invocation;
- restores config, runtime files, repository HEAD, and gateway state after any failure once mutation begins.

V3 success marker:

```text
NAILS_002E4_V3_DEPLOYMENT_OK
```

V3 is not authorized merely because it exists on a branch. It may be executed only after PR review, green CI, merge to `main`, and issuance of an exact approved release SHA by the main agent.

## NAILS-002E4 V2 — blocked after verified rollback

`ops/deploy/nails-002e4-v2.sh` must **not** be executed again.

The production attempt reached runtime installation and passed:

```text
CONFIG_UPDATED_ATOMICALLY=true
CONFIG_POSTSTATE_OK=true
PLUGIN_LIST_OK=true
```

It then failed inside its own read-only registry/visibility assertion. The failure was not evidence that `nails-scheduling` failed to install or appear in the plugin list.

Exact defect:

1. V2 converted `_get_platform_tools(...)` to a list and compared it with a fixed-order list, although the installed Hermes version returns a set-like, unordered collection.
2. V2 called `discover_plugins(force=True)` in a process where imports could already initialize bundled providers, producing the warning that dashboard-auth provider `basic` was already registered.

Rollback completed successfully:

```text
ROLLBACK_PERFORMED=true
ROLLBACK_TARGET_HEAD=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_HEAD_CURRENT=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_GATEWAY_STATE=active
```

The V2 file remains in Git as an auditable artifact. Its previous success marker was `NAILS_002E4_DEPLOYMENT_OK`, but that marker was never reached in production.

The following historical V2 statements remain true but do not authorize execution:

- it used root user-level systemd;
- it atomically updates structured YAML;
- it appends `nails-scheduling` to `plugins.enabled`;
- it appends `nails_scheduling` to `platform_toolsets.telegram`;
- “This runbook is not authorized merely because it exists on a branch.”

## NAILS-002E4 V1 — blocked legacy runbook

`ops/deploy/nails-002e4.sh` must **not** be executed again.

The first production attempt proved that two of its infrastructure assumptions were wrong:

1. it addressed `hermes-gateway-nails.service` through the system service manager, while the real gateway is a root user-level systemd service;
2. it searched for an assumed comma-separated tool allowlist, while the authoritative profile configuration is structured YAML at `/root/.hermes/profiles/nails/config.yaml`.

The script failed before repository or runtime mutation. It remains in Git only as an auditable record.

The correct gateway control boundary is:

```bash
XDG_RUNTIME_DIR=/run/user/0 systemctl --user \
  <status|show|stop|start|restart> hermes-gateway-nails.service
```

No deployment is authorized merely because an old E4 runbook exists in a release commit.
