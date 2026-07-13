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

## NAILS-002E4 V2 — corrected deployment runbook

Eligible runbook after merge and explicit release approval:

```text
ops/deploy/nails-002e4-v2.sh
```

It corrects both invalid assumptions from the first attempt:

- addresses `hermes-gateway-nails.service` through root user-level systemd using `XDG_RUNTIME_DIR=/run/user/0 systemctl --user`;
- parses and atomically updates `/root/.hermes/profiles/nails/config.yaml` as structured YAML.

The runbook:

- requires the verified production baseline `5565a524b75a04fe5d8bc2c3e758d2994e9d9c12`;
- verifies the approved release contains the reviewed scheduling implementation and infrastructure contracts;
- verifies Hermes Agent `v0.18.2 (2026.7.7.2)` and the exact import path;
- verifies the root user-level unit, fragment, process command, parent manager, PID, restart policy, and current active state;
- verifies the existing onboarding plugin remains the only enabled Nails plugin before mutation;
- verifies the exact semantic YAML pre-state;
- creates a root-only backup before any production mutation;
- fast-forwards the repository to the exact approved release SHA;
- installs only the reviewed scheduling plugin files and scheduling skill;
- appends `nails-scheduling` to `plugins.enabled` without replacing `nails-onboarding`;
- explicitly appends `nails_scheduling` to `platform_toolsets.telegram`;
- keeps `plugins.entries.nails-onboarding`, `toolsets`, `tools.tool_search`, and `agent.disabled_toolsets` unchanged;
- validates Hermes config, plugin discovery, registered tools/toolsets, and Telegram tool definitions before and after the gateway restart;
- stops and starts only the root user-level Nails gateway;
- proves `nails-api`, `nails-db`, and the Docker daemon were not restarted or replaced;
- performs no migration, SQL, backend deployment, backend restart, or plugin tool invocation;
- restores config, runtime files, repository HEAD, and gateway state on any failure after mutation begins;
- reports `ROLLBACK_PERFORMED=false` for failures before production mutation starts.

Success marker:

```text
NAILS_002E4_DEPLOYMENT_OK
```

This runbook is not authorized merely because it exists on a branch. It may be executed only after PR review, green CI, merge to `main`, and issuance of an exact approved release SHA by the main agent.

## NAILS-002E4 — blocked legacy runbook

`nails-002e4.sh` must **not** be executed again.

The first production attempt proved that two of its infrastructure assumptions were wrong:

1. it addressed `hermes-gateway-nails.service` through the system service manager, while the real gateway is a root user-level systemd service;
2. it searched for an assumed comma-separated tool allowlist, while the authoritative profile configuration is structured YAML at `/root/.hermes/profiles/nails/config.yaml`.

The script failed before repository or runtime mutation, but its service and configuration logic is superseded. It remains in Git only as an auditable record of the failed deployment attempt.

The correct gateway control boundary is:

```bash
XDG_RUNTIME_DIR=/run/user/0 systemctl --user \
  <status|show|stop|start|restart> hermes-gateway-nails.service
```

No deployment is authorized merely because `nails-002e4.sh` exists in a release commit.
