# Hermes plugin runtime contract for Nails

Last verified on production: **2026-07-13 21:58 UTC**.

This document records the exact plugin-loading and Telegram tool-visibility behavior of the Hermes installation used by the Nails profile. Read it together with [`production-infrastructure.md`](production-infrastructure.md) and [`../context/current.md`](../context/current.md) before changing profile plugins or tool configuration.

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

A deployment runbook must verify the installed version and import path before relying on this contract. A Hermes upgrade requires a separate review and a fresh verification of plugin discovery and tool visibility.

## 2. Profile-local plugin discovery

Profile-local plugins are discovered under:

```text
/root/.hermes/profiles/nails/plugins
```

For standalone/user plugins in this Hermes version, placing a directory there is not enough. The plugin key or manifest name must also appear in:

```yaml
plugins:
  enabled: []
```

The directory can use an underscore while plugin key and manifest name use a hyphen.

Onboarding identity:

```text
runtime directory: /root/.hermes/profiles/nails/plugins/nails_onboarding
plugin key: nails-onboarding
manifest name: nails-onboarding
manifest version: 0.5.0
tool name: nails_onboarding
toolset: nails_onboarding
currently loaded: true
```

Scheduling identity:

```text
runtime directory: /root/.hermes/profiles/nails/plugins/nails_scheduling
plugin key: nails-scheduling
manifest name: nails-scheduling
manifest version: 0.1.0
tool name: nails_scheduling
toolset: nails_scheduling
currently loaded: true
```

Configuration must use plugin keys/manifest names:

```text
nails-onboarding
nails-scheduling
```

It must not use directory or tool names `nails_onboarding` and `nails_scheduling` inside `plugins.enabled`.

## 3. Verified current production configuration

Authoritative file:

```text
/root/.hermes/profiles/nails/config.yaml
```

Relevant semantic state after successful NAILS-002E4 V3 deployment:

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

The config is structured YAML. It must be parsed semantically, backed up, changed atomically, parsed again, and checked with Hermes. String search-and-replace of a fabricated comma-separated allowlist is forbidden.

## 4. Registration contract

Onboarding registration is equivalent to:

```python
ctx.register_tool(
    name="nails_onboarding",
    toolset="nails_onboarding",
    ...,
)
```

Scheduling registration is equivalent to:

```python
ctx.register_tool(
    name="nails_scheduling",
    toolset="nails_scheduling",
    ...,
)
```

Both plugins must be enabled simultaneously. Adding a new plugin must extend `plugins.enabled`; it must not replace or remove the working onboarding plugin.

## 5. Explicit Telegram boundary

The Telegram list is kept explicit so the model-visible boundary can be reviewed and asserted:

```yaml
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

Although this Hermes version can auto-enable previously unknown plugin toolsets, production runbooks must not rely on that implicit behavior.

No E4 deployment change was required to:

```text
toolsets
custom_toolsets
tools.tool_search
agent.disabled_toolsets
plugins.disabled
plugins.entries.nails-onboarding
```

## 6. Correct read-only verification semantics

Read-only plugin list:

```bash
HERMES_HOME=/root/.hermes/profiles/nails \
/usr/local/lib/hermes-agent/venv/bin/hermes \
  --profile nails plugins list --plain --no-bundled
```

Expected Nails entries:

```text
enabled user 0.5.0 nails-onboarding
enabled user 0.1.0 nails-scheduling
```

The installed Python runtime must verify:

```text
plugin nails-onboarding is enabled and has no load error
plugin nails-scheduling is enabled and has no load error
registered Nails toolsets = nails_onboarding,nails_scheduling
registered Nails tools = nails_onboarding,nails_scheduling
Telegram definitions contain both tools
```

Two production-specific rules are mandatory:

### 6.1 Plugin discovery must be idempotent

Use:

```python
discover_plugins()
```

Do not use:

```python
discover_plugins(force=True)
```

in a verification interpreter where imported Hermes modules may already initialize bundled providers. Forced rediscovery produced this warning during the V2 attempt:

```text
Plugin 'basic' failed to register dashboard-auth provider 'basic':
dashboard-auth provider already registered: 'basic'
```

The warning was caused by duplicate registration of a built-in provider, not by `nails-scheduling`.

### 6.2 Platform toolsets are unordered

In Hermes Agent `v0.18.2`, `_get_platform_tools(config, "telegram")` returns a set-like unordered collection. Compare exact membership:

```python
telegram_toolsets = set(_get_platform_tools(config, "telegram"))
assert telegram_toolsets == expected_telegram_toolsets
```

Do not convert it to a list and compare iteration order. The fixed-order assertion caused the V2 rollback even though `PLUGIN_LIST_OK=true` had already proved both plugins loaded.

Sort only when an API explicitly requires a deterministic sequence:

```python
get_tool_definitions(enabled_toolsets=sorted(telegram_toolsets), ...)
```

## 7. Successful V3 production evidence

Successful runbook:

```text
ops/deploy/nails-002e4-v3.sh
release: 385a92962e3736553335d717adcdf4b83ac8a8b3
success marker: NAILS_002E4_V3_DEPLOYMENT_OK
```

Verified markers:

```text
PLUGIN_LIST_OK=true
PLUGIN_REGISTRY_OK=true
TELEGRAM_VISIBILITY_OK=true
KEYS_MATCH=true
plugin_discovery=idempotent
plugin_registry=ok
telegram_visibility=ok
gateway_error_scan=clean
```

A short startup journal can contain zero literal mentions of `nails_onboarding` or `nails_scheduling`. Zero mention count is not a failure when plugin list, registry and generated Telegram definitions all pass and the gateway error scan is clean.

`getMe`, plugin list and generated definitions still do not replace manual Telegram acceptance. The user-facing happy path, duplicate protection, invalid slot, overlap rejection and log privacy checks remain required.

## 8. Failed attempt and rollback reference

V2 is permanently blocked:

```text
ops/deploy/nails-002e4-v2.sh
```

It failed only in read-only verification and then restored the original state:

```text
ROLLBACK_PERFORMED=true
ROLLBACK_HEAD_CURRENT=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_GATEWAY_STATE=active
```

Full record:

[`../deployments/2026-07-13-nails-002e4-v2-rollback.md`](../deployments/2026-07-13-nails-002e4-v2-rollback.md).

## 9. Safety boundary

A plugin deployment must not:

- replace or remove `nails-onboarding` from `plugins.enabled`;
- enable generic HTTP, terminal, filesystem, browser, code execution, SQL, SSH, deployment, MCP, or other broad tools;
- print `config.yaml`, profile environment, Telegram identifiers, or secrets in full;
- rebuild or restart `nails-api`, `nails-db`, or Docker;
- call `nails_onboarding` or `nails_scheduling` during infrastructure installation;
- compare unordered toolsets by list iteration order;
- force plugin rediscovery in a way that repeats bundled provider registration;
- continue when installed Hermes version, current YAML state, plugin list or root user-level systemd topology differs from this contract.

On any mismatch, stop and return the evidence to the main agent for a reviewed change through GitHub.
