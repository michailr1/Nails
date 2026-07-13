# Production diagnostic runbooks

Diagnostic scripts are written, reviewed, and merged by the main ChatGPT agent. The VPS agent only executes an exact script from an approved Git commit and returns its sanitized output.

Diagnostics in this directory must be read-only. They may inspect service metadata, repository state, file metadata, health endpoints, and sanitized logs. They must not start, stop, restart, enable, disable, reset, edit, copy, remove, install, migrate, or otherwise change production state.

## Gateway preflight diagnostic

`gateway-nails-preflight.sh` explains why `hermes-gateway-nails.service` is not active before deployment. It records:

- current repository HEAD, branch, and clean-tree state;
- backend health and readiness;
- systemd load, active/sub states, result, exit status, restart policy, timestamps, unit path, and file metadata;
- Nails Hermes profile metadata and old allowlist match count;
- the last gateway journal lines after redacting tokens, secrets, long hexadecimal values, UUIDs, and user/chat/Telegram identifiers.

It always reports `changes_executed=false` and contains no service or filesystem mutation commands.

The main agent supplies the exact `NAILS_DIAGNOSTIC_SHA` after merge. Execution shape:

```bash
bash -lc '
set -Eeuo pipefail
cd /opt/nails/repo
git fetch origin main
export NAILS_DIAGNOSTIC_SHA="<EXACT_APPROVED_DIAGNOSTIC_SHA>"
git show "${NAILS_DIAGNOSTIC_SHA}:ops/diagnostics/gateway-nails-preflight.sh" | bash
'
```
