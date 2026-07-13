# Production deployment runbooks

These scripts are authored, reviewed, and merged by the main ChatGPT agent. The VPS agent never writes or edits them and never substitutes its own commands.

## Execution contract

A production runbook is executed only from an exact release commit approved by the main agent. The production checkout may still be on the previous release, so the VPS agent reads the script directly from the fetched Git object and pipes it to Bash without creating or editing a local copy.

The main agent supplies the final 40-character `NAILS_RELEASE_SHA` after merge. The execution shape is:

```bash
bash -lc '
set -Eeuo pipefail
cd /opt/nails/repo
git fetch origin main
export NAILS_RELEASE_SHA="<EXACT_APPROVED_RELEASE_SHA>"
git show "${NAILS_RELEASE_SHA}:ops/deploy/nails-002e4.sh" | bash
'
```

The placeholder is never resolved by the VPS agent. It is replaced by the main agent in the exact deployment prompt.

## NAILS-002E4

`nails-002e4.sh` deploys the restricted Hermes scheduling integration. It:

- requires the production checkout to be the recorded pre-release SHA;
- verifies `origin/main` equals the approved release SHA;
- verifies the approved release contains the reviewed scheduling implementation;
- backs up the current runtime plugin, skill, allowlist, and original HEAD;
- fast-forwards the checkout to the approved release;
- installs only the exact scheduling runtime files and skill;
- expands only the agreed Hermes tool allowlist;
- restarts only `hermes-gateway-nails.service`;
- verifies the backend container was not restarted or replaced;
- performs the predefined rollback on any failed assertion.

It does not run migrations, SQL, backend rebuilds, backend restarts, GitHub writes, or application-code edits.
