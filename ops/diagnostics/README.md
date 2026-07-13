# Production diagnostic runbooks

Diagnostic scripts are written, reviewed, and merged by the main ChatGPT agent. The VPS agent only executes an exact script from an approved Git commit and returns its sanitized output.

Diagnostics in this directory must be read-only. They may inspect service metadata, repository state, file metadata, health endpoints, processes, containers, sessions, schedulers, sockets, and sanitized logs. They must not start, stop, restart, enable, disable, reset, edit, copy, remove, install, migrate, or otherwise change production state.

## Gateway preflight diagnostic

`gateway-nails-preflight.sh` explains why `hermes-gateway-nails.service` is not active before deployment. It records:

- current repository HEAD, branch, and clean-tree state;
- backend health and readiness;
- systemd load, active/sub states, result, exit status, restart policy, timestamps, unit path, and file metadata;
- Nails Hermes profile metadata and old allowlist match count;
- the last gateway journal lines after redacting tokens, secrets, long hexadecimal values, UUIDs, and user/chat/Telegram identifiers.

It always reports `changes_executed=false` and contains no service or filesystem mutation commands.

## Hermes runtime discovery

`hermes-runtime-discovery.sh` is used when the expected systemd unit does not exist. It searches read-only for the actual Hermes runtime launcher across:

- loaded system services, service files, and timers;
- root user-systemd services and unit files;
- matching unit files in known system and user unit directories, including sanitized contents;
- active processes and listening sockets;
- Docker containers;
- tmux and screen sessions;
- root and system cron entries;
- runtime-related artifacts under the Nails Hermes profile;
- recent global journal entries matching Hermes, Nails, gateway, or Telegram terms.

Potential secrets, bot tokens, API keys, authorization values, UUIDs, long hexadecimal values, long numeric identifiers, and URL query values are redacted before output. It always reports `changes_executed=false`.

## Immutable execution

The main agent supplies the exact `NAILS_DIAGNOSTIC_SHA` after merge. The VPS agent never edits or copies a diagnostic script.

Gateway preflight execution shape:

```bash
bash -lc '
set -Eeuo pipefail
cd /opt/nails/repo
git fetch origin main
export NAILS_DIAGNOSTIC_SHA="<EXACT_APPROVED_DIAGNOSTIC_SHA>"
git show "${NAILS_DIAGNOSTIC_SHA}:ops/diagnostics/gateway-nails-preflight.sh" | bash
'
```

Runtime discovery execution shape:

```bash
bash -lc '
set -Eeuo pipefail
cd /opt/nails/repo
git fetch origin main
export NAILS_DIAGNOSTIC_SHA="<EXACT_APPROVED_DIAGNOSTIC_SHA>"
git show "${NAILS_DIAGNOSTIC_SHA}:ops/diagnostics/hermes-runtime-discovery.sh" | bash
'
```
