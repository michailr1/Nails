# Hermes plugin runtime contract for Nails

Last verified on production: **2026-07-14**.

This document records the exact plugin-loading and Telegram tool-visibility behavior of the Hermes installation used by the Nails profile. Read it together with [`production-infrastructure.md`](production-infrastructure.md) before changing profile plugins or tool configuration.

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

The production onboarding plugin proves this behavior:

```text
runtime directory: /root/.hermes/profiles/nails/plugins/nails_onboarding
plugin key: nails-onboarding
manifest name: nails-onboarding
manifest version: 0.5.0
tool name: nails_onboarding
toolset: nails_onboarding
currently loaded: true
```

Its registration is equivalent to:

```python
ctx.register_tool(
    name="nails_onboarding",
    toolset="nails_onboarding",
    ...,
)
```

The directory uses an underscore, while the plugin key and manifest name use a hyphen. Configuration must use the plugin key/manifest name:

```text
nails-onboarding
```

It must not use the directory name `nails_onboarding` in `plugins.enabled`.

## 3. Verified pre-deployment configuration

Authoritative file:

```text
/root/.hermes/profiles/nails/config.yaml
```

Relevant semantic state before NAILS-002E4:

```yaml
plugins:
  enabled:
    - nails-onboarding
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
```

`custom_toolsets` is absent.

The config is structured YAML. It must be parsed semantically, backed up, changed atomically, parsed again, and checked with Hermes. String search-and-replace of a fabricated comma-separated allowlist is forbidden.

## 4. Scheduling plugin identity

Repository source:

```text
/opt/nails/repo/hermes/plugins/nails_scheduling
```

Expected runtime state after deployment:

```text
runtime directory: /root/.hermes/profiles/nails/plugins/nails_scheduling
plugin key: nails-scheduling
manifest name: nails-scheduling
manifest version: 0.1.0
tool name: nails_scheduling
toolset: nails_scheduling
```

Registration:

```python
ctx.register_tool(
    name="nails_scheduling",
    toolset="nails_scheduling",
    ...,
)
```

## 5. Approved configuration transition

The existing `plugins.enabled` list must be extended, not replaced.

Before:

```yaml
plugins:
  enabled:
    - nails-onboarding
```

After:

```yaml
plugins:
  enabled:
    - nails-onboarding
    - nails-scheduling
```

The existing onboarding entry remains unchanged:

```yaml
plugins:
  entries:
    nails-onboarding:
      allow_tool_override: false
```

For deterministic least-privilege Telegram configuration, the deployment also explicitly extends the Telegram toolset list:

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

Although this Hermes version can auto-enable previously unknown plugin toolsets, production runbooks must not rely on that implicit behavior. The Telegram list is kept explicit so the model-visible boundary can be reviewed and asserted exactly.

No change is required to:

```text
toolsets
custom_toolsets
tools.tool_search
agent.disabled_toolsets
plugins.disabled
plugins.entries.nails-onboarding
```

## 6. Required post-change checks

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

The deployment must also verify through the installed Python runtime that:

```text
plugin nails-onboarding is enabled and has no load error
plugin nails-scheduling is enabled and has no load error
registered Nails toolsets = nails_onboarding,nails_scheduling
registered Nails tools = nails_onboarding,nails_scheduling
Telegram definitions contain both tools
```

`getMe` or a successful plugin list does not replace manual Telegram acceptance. After deployment, the user-facing happy path, duplicate protection, invalid slot, overlap rejection, and log privacy checks are still required.

## 7. Safety boundary

A plugin deployment must not:

- replace or remove `nails-onboarding` from `plugins.enabled`;
- enable generic HTTP, terminal, filesystem, browser, code execution, SQL, SSH, deployment, MCP, or other broad tools;
- print `config.yaml`, profile environment, Telegram identifiers, or secrets in full;
- rebuild or restart `nails-api`, `nails-db`, or Docker;
- call `nails_onboarding` or `nails_scheduling` during infrastructure installation;
- continue when the installed Hermes version, current YAML state, plugin list, or root user-level systemd topology differs from this contract.

On any mismatch, stop and return the evidence to the main agent for a reviewed change through GitHub.
