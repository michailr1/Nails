# Production deployment runbooks

These scripts are authored, reviewed, and merged by the main ChatGPT agent. The VPS agent never writes or edits them and never substitutes its own commands.

Before preparing or executing any production runbook, read:

- [`../../AGENTS.md`](../../AGENTS.md);
- [`../../docs/operations/agent-responsibilities.md`](../../docs/operations/agent-responsibilities.md);
- [`../../docs/operations/production-infrastructure.md`](../../docs/operations/production-infrastructure.md).

The production infrastructure document is the source of truth for the service manager, runtime paths, profile configuration, and restart boundary. Runbooks must not reconstruct those facts from chat memory.

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

The placeholder is never resolved by the VPS agent. It is replaced by the main agent in the exact deployment prompt.

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

The next E4 deployment requires a new reviewed runbook with a new filename. It must:

- verify the root user-level unit is loaded and active;
- back up and parse `/root/.hermes/profiles/nails/config.yaml` as YAML;
- verify the actual installed Hermes plugin-discovery/tool-search contract before changing configuration;
- install only reviewed scheduling plugin and skill files;
- restart only the root user-level Nails gateway;
- prove backend container identity and start time are unchanged;
- provide an exact rollback that restores the YAML config, runtime files, repository HEAD, and gateway state.

No deployment is authorized merely because `nails-002e4.sh` exists in a release commit.
