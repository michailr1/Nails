# Nails production infrastructure — source of truth

Last verified: **2026-07-13 21:11 UTC**.

This document records the production topology that was verified directly on `de.funti.cc`. It must be read before preparing any production diagnostic, deployment, restart, or rollback runbook.

The document deliberately separates stable infrastructure facts from transient observations. A PID, container ID, start timestamp, current Git HEAD, and current configuration values must always be re-read during preflight and must not be treated as permanent constants.

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
/root/.hermes/profiles/nails       700 root:root
/root/.hermes/profiles/nails/.env  600 root:root
```

Secrets, Telegram identifiers, API keys, passwords, and complete environment-file contents must never be committed, printed, or included in reports.

## 2. Backend runtime

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

The backend and Hermes have independent lifecycles. A Hermes-only plugin or skill deployment must not rebuild or restart `nails-api`, `nails-db`, Docker, or the Docker daemon.

## 3. Hermes installation and profile

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

## 4. Hermes service manager: root user-level systemd

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

A production runbook must verify at minimum:

```text
LoadState=loaded
ActiveState=active
SubState=running
MainPID is a positive integer
FragmentPath=/root/.config/systemd/user/hermes-gateway-nails.service
```

The observed PID `2119629` was only a diagnostic snapshot. It is not a deployment constant and changes after restart.

## 5. Telegram transport

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

Telegram tokens, bot usernames when unnecessary, user IDs, and chat IDs must not be stored in this repository or included in production reports.

## 6. Hermes profile configuration

Authoritative production configuration file:

```text
/root/.hermes/profiles/nails/config.yaml
```

Relevant values observed on 2026-07-13 before the scheduling-tool deployment:

```yaml
toolsets:
  - hermes-cli
tools:
  tool_search:
    enabled: auto
    threshold_pct: 10
    search_default_limit: 5
    max_search_limit: 20
```

This is a structured YAML configuration. Deployment logic must parse and update the relevant YAML structure deliberately. It must not search for or replace an assumed comma-separated allowlist string.

The exact mechanism by which profile-local plugins are exposed to `tool_search` must be verified against the installed Hermes runtime before changing `config.yaml`. Do not invent a legacy allowlist representation merely because a previous runbook expected one.

Before any configuration change:

1. record the file path, ownership, mode, and SHA-256 without printing secrets;
2. create a root-only backup;
3. parse the YAML and assert the exact expected pre-state;
4. change only the reviewed keys;
5. parse the result again;
6. restart only the root user-level Nails gateway;
7. verify plugin discovery, logs, Telegram acceptance, and unchanged backend container identity.

## 7. Negative topology facts

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

Do not assume these negative facts remain true forever. A deployment preflight should still verify the actual parent process, unit fragment path, and command line.

## 8. Safe preflight template

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

Never print `/opt/nails/.env`, the Hermes profile `.env`, Telegram tokens, internal API keys, or full process environments.

## 9. Source-of-truth and update rule

For production work, use this order:

1. this infrastructure document for stable paths and service topology;
2. the exact merged deployment or diagnostic runbook for the current task;
3. a fresh read-only production preflight for transient state;
4. the VPS-agent report as evidence of what actually happened.

When production observation contradicts this document, stop the deployment. Update this document through branch, PR, CI, and merge before preparing the corrected production runbook.
