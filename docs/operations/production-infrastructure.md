# Nails production infrastructure — source of truth

Last verified: **2026-07-13 21:58 UTC**.

This document records the production topology verified directly on `de.funti.cc`. It must be read together with [`../context/current.md`](../context/current.md) before preparing any production diagnostic, deployment, restart, or rollback runbook.

The document deliberately separates stable infrastructure facts from transient observations. A PID, container ID, start timestamp, current Git HEAD and current configuration values must always be re-read during preflight and must not be treated as permanent constants.

## 1. Stable production identity

```text
hostname: de.funti.cc
repository: /opt/nails/repo
backend environment: /opt/nails/.env
backend API: http://127.0.0.1:8210
Hermes profile: /root/.hermes/profiles/nails
Hermes profile environment: /root/.hermes/profiles/nails/.env
Hermes profile config: /root/.hermes/profiles/nails/config.yaml
```

Expected permissions verified on 2026-07-13:

```text
/root/.hermes/profiles/nails             700 root:root
/root/.hermes/profiles/nails/.env        600 root:root
/root/.hermes/profiles/nails/config.yaml 600 root:root
```

Secrets, Telegram identifiers, API keys, passwords and complete environment-file contents must never be committed, printed or included in reports.

## 2. Current production snapshot

Successful scheduling release:

```text
HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3
branch: main
working tree: clean
Alembic: 0006
```

Successful runbook:

```text
ops/deploy/nails-002e4-v3.sh
NAILS_002E4_V3_DEPLOYMENT_OK
```

Backup:

```text
/root/.hermes/profiles/nails/backups/nails-002e4-v3-20260713T215800Z
```

This snapshot is a handoff aid, not a permanent preflight constant. A future runbook must still re-read the current HEAD, tree state, migrations and service state.

## 3. Backend runtime

The backend is a Docker Compose project with these application containers:

```text
nails-api
nails-db
```

Hermes is **not** running in Docker.

Backend health endpoints:

```bash
curl -fsS http://127.0.0.1:8210/health
curl -fsS http://127.0.0.1:8210/ready
```

The backend and Hermes have independent lifecycles. A Hermes-only plugin or skill deployment must not rebuild or restart `nails-api`, `nails-db`, Docker or the Docker daemon.

The successful V3 deployment proved:

```text
backend_api_container_unchanged=true
backend_db_container_unchanged=true
docker_daemon_unchanged=true
backend_health=ok
backend_ready=ok
migration_executed=false
database_write_executed=false
backend_restart_executed=false
```

## 4. Hermes installation and profile

Hermes executable environment:

```text
installation root: /usr/local/lib/hermes-agent
Python: /usr/local/lib/hermes-agent/venv/bin/python
profile name: nails
working directory: /root/.hermes/profiles/nails
HERMES_HOME: /root/.hermes/profiles/nails
```

Gateway command:

```text
/usr/local/lib/hermes-agent/venv/bin/python -m hermes_cli.main --profile nails gateway run
```

Repository sources and production runtime paths:

```text
repository onboarding plugin: hermes/plugins/nails_onboarding
runtime onboarding plugin: /root/.hermes/profiles/nails/plugins/nails_onboarding
repository scheduling plugin: hermes/plugins/nails_scheduling
runtime scheduling plugin: /root/.hermes/profiles/nails/plugins/nails_scheduling
repository onboarding skill: hermes/skills/nails-onboarding/SKILL.md
runtime onboarding skill: /root/.hermes/profiles/nails/skills/nails-onboarding/SKILL.md
repository scheduling skill: hermes/skills/nails-scheduling/SKILL.md
runtime scheduling skill: /root/.hermes/profiles/nails/skills/nails-scheduling/SKILL.md
```

## 5. Hermes service manager: root user-level systemd

The Nails gateway is managed by **root user-level systemd**, not by the system service manager.

```text
unit: hermes-gateway-nails.service
unit file: /root/.config/systemd/user/hermes-gateway-nails.service
manager parent: /usr/lib/systemd/systemd --user
UnitFileState: enabled
Restart: always
```

The system-level command below is wrong for this service and normally returns `not-found`:

```bash
systemctl status hermes-gateway-nails.service
```

All runbooks must address the root user manager explicitly:

```bash
XDG_RUNTIME_DIR=/run/user/0 systemctl --user status hermes-gateway-nails.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user show hermes-gateway-nails.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user stop hermes-gateway-nails.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user start hermes-gateway-nails.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user restart hermes-gateway-nails.service
```

The same rule applies to journal inspection:

```bash
XDG_RUNTIME_DIR=/run/user/0 journalctl --user \
  -u hermes-gateway-nails.service --no-pager
```

A running production gateway must verify at minimum:

```text
LoadState=loaded
ActiveState=active
SubState=running
MainPID is a positive integer
FragmentPath=/root/.config/systemd/user/hermes-gateway-nails.service
```

PIDs are transient. Observed examples `2119629`, `2308856` and `2318431` are diagnostic snapshots only and must never become deployment constants.

### Controlled stop behavior

During V3, `systemctl --user is-active` returned:

```text
failed
```

while `MainPID=0`. The runbook accepted `inactive` or `failed` only during the bounded stop phase and only when no process remained. This is not an acceptable final state.

After start, the unit must return to:

```text
ActiveState=active
SubState=running
MainPID is a new positive integer
```

The V3 deployment confirmed that transition.

## 6. Telegram transport

The Nails Telegram bot uses long polling through the Hermes gateway.

Verified transport facts:

```text
Telegram token present in profile environment: yes
getMe: successful
webhook configured: no
pending updates at verification time: 0
last Telegram API error present: no
```

A successful `getMe` or `getWebhookInfo` call proves token/API reachability but does not by itself prove an end-to-end user reply. Manual Telegram acceptance remains required after a gateway/plugin deployment.

Telegram tokens, bot usernames when unnecessary, user IDs and chat IDs must not be stored in this repository or included in production reports.

## 7. Hermes profile configuration

Authoritative production configuration file:

```text
/root/.hermes/profiles/nails/config.yaml
```

Relevant current values:

```yaml
plugins:
  enabled:
    - nails-onboarding
    - nails-scheduling
  disabled: []
  entries:
    nails-onboarding:
      allow_tool_override: false

toolsets:
  - hermes-cli

tools:
  tool_search:
    enabled: auto
    threshold_pct: 10
    search_default_limit: 5
    max_search_limit: 20

agent:
  disabled_toolsets:
    - kanban

platform_toolsets:
  telegram:
    - vision
    - image_gen
    - tts
    - skills
    - clarify
    - nails_onboarding
    - nails_scheduling
```

This is a structured YAML configuration. Deployment logic must parse and update the relevant YAML structure deliberately. It must not search for or replace an assumed comma-separated allowlist string.

The exact mechanism by which profile-local plugins are exposed to Telegram and tool definitions is recorded in [`hermes-plugin-runtime.md`](hermes-plugin-runtime.md). Do not invent a legacy allowlist representation merely because an old runbook expected one.

Before any configuration change:

1. record file path, ownership, mode and SHA-256 without printing secrets;
2. create a root-only backup;
3. parse YAML and assert the exact expected pre-state;
4. change only reviewed keys;
5. atomically replace the file;
6. parse and assert the result again;
7. restart only the root user-level Nails gateway;
8. verify plugin discovery, registry, Telegram definitions, logs and unchanged backend container identity.

## 8. Known failed deployment assumptions

Never repeat these assumptions:

### V1

- system-level systemd for the Nails gateway;
- comma-separated allowlist inside config.

### V2

- `_get_platform_tools(...)` has stable list order;
- `discover_plugins(force=True)` is harmless after imports may initialize bundled providers.

V1 and V2 are blocked. The detailed V2 rollback is stored in [`../deployments/2026-07-13-nails-002e4-v2-rollback.md`](../deployments/2026-07-13-nails-002e4-v2-rollback.md).

## 9. Negative topology facts

The following alternate launch mechanisms were checked and were not used for the Nails gateway at the verification time:

```text
system-level systemd service: no
Docker container: no
tmux: no
screen: no
root cron: no
supervisor: no evidence
PM2: not installed
nohup or unmanaged shell process: no evidence
```

Do not assume these negative facts remain true forever. A deployment preflight should still verify actual parent process, unit fragment path and command line.

## 10. Safe preflight template

Read-only identity checks:

```bash
hostname -f
git -C /opt/nails/repo branch --show-current
git -C /opt/nails/repo status --porcelain
git -C /opt/nails/repo rev-parse HEAD
curl -fsS http://127.0.0.1:8210/health
curl -fsS http://127.0.0.1:8210/ready
XDG_RUNTIME_DIR=/run/user/0 systemctl --user show \
  hermes-gateway-nails.service \
  -p LoadState \
  -p ActiveState \
  -p SubState \
  -p MainPID \
  -p FragmentPath \
  -p UnitFileState \
  -p Restart
```

Never print `/opt/nails/.env`, the Hermes profile `.env`, Telegram tokens, internal API keys or full process environments.

## 11. Source-of-truth and update rule

For production work, use this order:

1. [`../context/current.md`](../context/current.md) for the current task and continuation point;
2. this infrastructure document for stable paths and service topology;
3. [`hermes-plugin-runtime.md`](hermes-plugin-runtime.md) for plugin discovery and tool visibility;
4. the exact merged deployment or diagnostic runbook for the current task;
5. a fresh read-only production preflight for transient state;
6. the VPS-agent report as evidence of what actually happened.

When production observation contradicts these documents, stop the deployment. Update the relevant source of truth through branch, PR, CI and merge before preparing a corrected production runbook.
