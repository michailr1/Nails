# NAILS-002E4 V2 — production rollback report

Date: **2026-07-13 UTC**

Status: **deployment failed safely; rollback completed**.

## Baseline

```text
host: de.funti.cc
production HEAD before: 5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
attempted release: b529b577fdaed5c8c1cfbcdbe24bce79a419004f
runbook: ops/deploy/nails-002e4-v2.sh
```

## Successful stages before failure

The runbook proved the expected production pre-state:

```text
CONFIG_PRESTATE_OK=true
ONBOARDING_PLUGIN_PRECHECK=true
KEYS_MATCH=true
```

It then:

1. created the root-only backup;
2. fast-forwarded the repository to the approved release;
3. validated the scheduling release sources;
4. stopped only the root user-level Nails gateway;
5. installed the reviewed scheduling plugin and skill;
6. atomically updated structured Hermes YAML;
7. parsed and verified the exact config post-state;
8. verified both plugins through the Hermes CLI.

The last successful markers were:

```text
CONFIG_UPDATED_ATOMICALLY=true
CONFIG_POSTSTATE_OK=true
PLUGIN_LIST_OK=true
```

`PLUGIN_LIST_OK=true` means Hermes reported both expected user plugins:

```text
enabled user 0.5.0 nails-onboarding
enabled user 0.1.0 nails-scheduling
```

## Failure

The subsequent read-only Python verification printed:

```text
Plugin 'basic' failed to register dashboard-auth provider 'basic':
dashboard-auth provider already registered: 'basic'
```

and then raised a bare assertion at line 30 of the embedded snippet.

Line mapping proved that the failing assertion was the exact ordered-list comparison for:

```python
telegram_toolsets = list(_get_platform_tools(cfg, "telegram"))
```

The deployment incorrectly assumed iteration order. In Hermes Agent `v0.18.2 (2026.7.7.2)`, `_get_platform_tools` returns a set-like, unordered collection. Membership was correct, but list order was not a stable contract.

The `basic` message was separately caused by calling:

```python
discover_plugins(force=True)
```

inside a process whose imports could already initialize bundled providers. Forced rediscovery attempted to register the built-in dashboard-auth provider again. It was diagnostic noise and was not the line that triggered rollback.

## Rollback evidence

The runbook executed its predefined rollback:

```text
ROLLBACK_PERFORMED=true
ROLLBACK_TARGET_HEAD=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_HEAD_CURRENT=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_GATEWAY_STATE=active
```

Therefore, after the attempt:

- repository HEAD returned to the original production baseline;
- profile config was restored from backup;
- scheduling plugin runtime files were removed/restored to their pre-state;
- scheduling skill was removed/restored to its pre-state;
- onboarding remained the enabled production plugin;
- the root user-level gateway returned to `active`;
- no database migration or SQL was executed;
- backend and Docker were not intentionally restarted by the runbook.

## Corrective action

V2 is permanently blocked.

The replacement `ops/deploy/nails-002e4-v3.sh`:

- calls `discover_plugins()` without `force=True`;
- converts Telegram toolsets to a set and verifies exact membership;
- passes a sorted toolset list only where a deterministic sequence is needed by `get_tool_definitions`;
- includes observed values in assertion failures;
- retains the full backup, rollback, root user-systemd, YAML, plugin, gateway, backend, and Docker boundaries.

Production deployment remains incomplete until V3 is merged, executed successfully, and followed by manual Telegram acceptance.
