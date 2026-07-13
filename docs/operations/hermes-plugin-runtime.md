# Hermes plugin runtime contract for Nails

Last verified on production: **2026-07-13 21:58 UTC**.

Read this document with [`production-infrastructure.md`](production-infrastructure.md) and [`../context/current.md`](../context/current.md) before changing profile plugins, skills or Telegram tool visibility.

## 1. Installed Hermes runtime

```text
Hermes Agent v0.18.2 (2026.7.7.2)
upstream: c44de998
local: af250d84 (+1 carried commit)
install method: git
install directory: /usr/local/lib/hermes-agent
Python: 3.11.15
Python executable: /usr/local/lib/hermes-agent/venv/bin/python
CLI executable: /usr/local/lib/hermes-agent/venv/bin/hermes
hermes_cli import: /usr/local/lib/hermes-agent/hermes_cli/__init__.py
```

A runbook must verify version and import path. A Hermes upgrade requires separate review.

## 2. Profile-local plugin discovery

Plugins are discovered under:

```text
/root/.hermes/profiles/nails/plugins
```

A runtime directory alone is insufficient. The plugin key/manifest name must appear in `plugins.enabled`.

Onboarding identity:

```text
runtime directory: /root/.hermes/profiles/nails/plugins/nails_onboarding
plugin key: nails-onboarding
manifest name: nails-onboarding
manifest version: 0.5.0
tool name: nails_onboarding
toolset: nails_onboarding
```

Scheduling production identity before E5:

```text
runtime directory: /root/.hermes/profiles/nails/plugins/nails_scheduling
plugin key: nails-scheduling
manifest name: nails-scheduling
manifest version: 0.1.0
tool name: nails_scheduling
toolset: nails_scheduling
```

Scheduling expected identity after successful E5:

```text
plugin key: nails-scheduling
manifest name: nails-scheduling
manifest version: 0.2.0
tool name: nails_scheduling
toolset: nails_scheduling
new actions: resolve_date, update_availability
```

The directory/tool names use underscores; `plugins.enabled` uses hyphenated plugin keys.

## 3. Authoritative config

```text
/root/.hermes/profiles/nails/config.yaml
```

Current and post-E5 semantic state must be identical:

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

`custom_toolsets` is absent.

The config is structured YAML. It must be parsed semantically. String replacement of a fabricated comma-separated allowlist is forbidden.

Although this Hermes version can auto-enable previously unknown plugin toolsets, production runbooks **must not rely on that implicit behavior**. Telegram visibility stays explicit.

## 4. Registration contract

Equivalent registration:

```python
ctx.register_tool(name="nails_onboarding", toolset="nails_onboarding", ...)
ctx.register_tool(name="nails_scheduling", toolset="nails_scheduling", ...)
```

Both plugins remain enabled. E5 updates scheduling runtime files and both skills; it does not replace plugin keys, toolsets or config.

## 5. Scheduling 0.2.0 model-visible actions

After E5, the generated `nails_scheduling` definition must include:

```text
resolve_date
list_services
day_view
free_slots
find_client
create_client
update_availability
create_booking
```

New security/UX rules:

- `resolve_date` delegates all calendar arithmetic to backend application time;
- the model does not calculate date, year or weekday itself;
- `update_availability` changes only explicitly named dates after a current/future summary and explicit confirmation;
- states are `available`, `unavailable`, `unknown`;
- unrelated dates are preserved;
- active bookings cannot be displaced;
- completed onboarding is not restarted for ordinary calendar corrections;
- deployment never invokes these actions and never changes calendar data.

## 6. Correct read-only verification

Plugin list command:

```bash
HERMES_HOME=/root/.hermes/profiles/nails \
/usr/local/lib/hermes-agent/venv/bin/hermes \
  --profile nails plugins list --plain --no-bundled
```

Expected before E5:

```text
enabled user 0.5.0 nails-onboarding
enabled user 0.1.0 nails-scheduling
```

Expected after E5:

```text
enabled user 0.5.0 nails-onboarding
enabled user 0.2.0 nails-scheduling
```

Required post-change markers:

```text
PLUGIN_LIST_OK=true
PLUGIN_REGISTRY_OK=true
TELEGRAM_VISIBILITY_OK=true
SCHEDULING_ACTIONS_OK=true
KEYS_MATCH=true
```

### 6.1 Discovery must be idempotent

Use:

```python
discover_plugins()
```

Do not use:

```python
discover_plugins(force=True)
```

Forced rediscovery previously attempted duplicate registration of built-in provider `basic`.

### 6.2 Platform toolsets are unordered

`_get_platform_tools(config, "telegram")` returns a **set-like unordered collection**. Compare exact set membership:

```python
telegram_toolsets = set(_get_platform_tools(config, "telegram"))
assert telegram_toolsets == expected_telegram_toolsets
```

Never compare list iteration order. Sort only when an API requires a deterministic sequence.

## 7. E5 deployment boundary

Approved candidate files:

```text
ops/deploy/nails-002e5-date-availability.sh
ops/deploy/lib/nails-002e5-common.sh
ops/deploy/lib/nails-002e5-runtime.sh
```

The deployment is a coordinated backend/Hermes release:

- build a new `nails-api` image while the old API remains online;
- stop only the root user-level Hermes gateway;
- recreate only `nails-api` with `--no-deps`;
- keep `nails-db` and Docker daemon unchanged;
- keep Alembic revision `0006` and reject release changes under `backend/alembic`;
- install scheduling plugin `0.2.0` and updated onboarding/scheduling skills;
- prove profile config did not change;
- verify OpenAPI routes, plugin registry, Telegram visibility and new actions;
- restore old image/runtime/repo/gateway on failure.

The prior generic rule “never rebuild nails-api during a plugin deployment” still applies to Hermes-only changes. E5 is not plugin-only: it is an explicitly reviewed coordinated backend/plugin deployment. It must not rebuild or restart `nails-db` or the Docker daemon.

E5 must not:

- execute ad-hoc SQL;
- change availability/calendar rows;
- invoke `nails_onboarding` or `nails_scheduling`;
- change `plugins.enabled`, `platform_toolsets` or other Hermes config;
- expose broad terminal, filesystem, HTTP, browser, SQL, SSH, GitHub, MCP or deployment tools;
- print secrets, Telegram identifiers or complete environment files.

## 8. Historical evidence

Successful E4 V3:

```text
release: 385a92962e3736553335d717adcdf4b83ac8a8b3
success marker: NAILS_002E4_V3_DEPLOYMENT_OK
```

V2 remains permanently blocked. It failed in read-only verification and rolled back successfully:

```text
ROLLBACK_PERFORMED=true
ROLLBACK_HEAD_CURRENT=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_GATEWAY_STATE=active
```

Manual Telegram acceptance remains mandatory after E5. Plugin list, registry and OpenAPI checks do not prove the user-facing resolver or confirmed calendar correction flow.
