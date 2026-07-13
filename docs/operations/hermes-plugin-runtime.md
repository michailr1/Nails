# Hermes plugin runtime contract for Nails

Last verified production runtime: **2026-07-13 21:58 UTC**.

Read with [`production-infrastructure.md`](production-infrastructure.md) and [`../context/current.md`](../context/current.md).

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

A Hermes upgrade requires separate review.

## 2. Plugin identity

Plugins are discovered under:

```text
/root/.hermes/profiles/nails/plugins
```

Onboarding:

```text
plugin key: nails-onboarding
manifest name: nails-onboarding
manifest version: 0.5.0
tool name: nails_onboarding
toolset: nails_onboarding
```

Scheduling allowed pre-E6 identities:

```text
plugin key: nails-scheduling
manifest name: nails-scheduling
tool name: nails_scheduling
toolset: nails_scheduling
manifest version: 0.1.0 when HEAD is 385a92962e3736553335d717adcdf4b83ac8a8b3
manifest version: 0.2.0 when HEAD is a0ef8c5c26301a9f6950544afd0e070b7e691582
```

Expected after E6:

```text
plugin key: nails-scheduling
manifest name: nails-scheduling
manifest version: 0.3.0
tool name: nails_scheduling
toolset: nails_scheduling
```

Directory/tool names use underscores; `plugins.enabled` uses hyphenated keys.

## 3. Authoritative config

```text
/root/.hermes/profiles/nails/config.yaml
```

Pre- and post-E6 semantic state is identical:

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

`custom_toolsets` is absent. The config is structured YAML and must be parsed semantically. String replacement of a fabricated comma-separated allowlist is forbidden.

Hermes can auto-enable unknown plugin toolsets, but runbooks **must not rely on that implicit behavior**. Telegram visibility remains explicit.

## 4. Registration and actions

Equivalent registration:

```python
ctx.register_tool(name="nails_onboarding", toolset="nails_onboarding", ...)
ctx.register_tool(name="nails_scheduling", toolset="nails_scheduling", ...)
```

Scheduling `0.3.0` must expose exactly:

```text
resolve_date
list_services
find_service
create_service
update_service
day_view
free_slots
find_client
create_client
update_availability
create_booking
```

Behavioral rules:

- backend resolves all dates, years and weekdays;
- `update_availability` changes only explicitly named dates after confirmation;
- `find_service`, `create_service` and `update_service` manage the operational catalog after onboarding;
- price, duration and buffer changes affect future bookings;
- existing bookings retain commercial and timing snapshots;
- service deletion is archive/reactivate, not physical deletion;
- onboarding is never restarted for ordinary calendar or service corrections;
- deployment never invokes these actions or changes business data.

## 5. Correct read-only verification

```bash
HERMES_HOME=/root/.hermes/profiles/nails \
/usr/local/lib/hermes-agent/venv/bin/hermes \
  --profile nails plugins list --plain --no-bundled
```

Allowed before E6:

```text
enabled user 0.5.0 nails-onboarding
enabled user 0.1.0 nails-scheduling
```

or:

```text
enabled user 0.5.0 nails-onboarding
enabled user 0.2.0 nails-scheduling
```

Expected after E6:

```text
enabled user 0.5.0 nails-onboarding
enabled user 0.3.0 nails-scheduling
```

Required markers:

```text
PLUGIN_LIST_OK=true
PLUGIN_REGISTRY_OK=true
TELEGRAM_VISIBILITY_OK=true
SCHEDULING_ACTIONS_OK=true
KEYS_MATCH=true
```

### Discovery must be idempotent

Use:

```python
discover_plugins()
```

Do not use:

```python
discover_plugins(force=True)
```

Forced rediscovery previously attempted duplicate registration of bundled provider `basic`.

### Platform toolsets are unordered

`_get_platform_tools(config, "telegram")` returns a **set-like unordered collection**:

```python
telegram_toolsets = set(_get_platform_tools(config, "telegram"))
assert telegram_toolsets == expected_telegram_toolsets
```

Never compare iteration order. Sort only when an API requires a sequence.

## 6. E6 deployment boundary

Candidate files:

```text
ops/deploy/nails-002e6-combined-operations.sh
ops/deploy/lib/nails-002e6-runtime.sh
ops/deploy/lib/nails-002e5-common.sh
```

E6:

- detects exact E4 `0.1.0` or E5 `0.2.0` baseline;
- builds a new `nails-api` image while the old API remains online;
- stops only the root user-level gateway;
- recreates only `nails-api` with `--no-deps`;
- keeps `nails-db` and Docker daemon unchanged;
- keeps Alembic revision `0006` and rejects changes under `backend/alembic`;
- installs scheduling `0.3.0` and both skills;
- proves profile config did not change;
- verifies date, availability and service-management routes and actions;
- restores the detected repository/image/runtime/config/gateway baseline on failure.

E6 must not:

- execute ad-hoc SQL;
- change calendar, service, client or booking rows;
- invoke `nails_onboarding` or `nails_scheduling`;
- change `plugins.enabled` or `platform_toolsets`;
- restart/recreate `nails-db` or Docker daemon;
- print secrets, Telegram identifiers or complete environment files.

## 7. Historical evidence

E4 V3 success:

```text
release: 385a92962e3736553335d717adcdf4b83ac8a8b3
success marker: NAILS_002E4_V3_DEPLOYMENT_OK
```

E5 candidate:

```text
release: a0ef8c5c26301a9f6950544afd0e070b7e691582
success marker: NAILS_002E5_DEPLOYMENT_OK
```

Its production result was not reported, so E6 supports both sides explicitly.

V2 rollback evidence:

```text
ROLLBACK_PERFORMED=true
ROLLBACK_HEAD_CURRENT=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_GATEWAY_STATE=active
```

Manual Telegram acceptance remains mandatory after E6. Plugin list, registry and OpenAPI checks do not prove the user-facing confirmation flows.
