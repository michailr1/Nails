# Nails onboarding Hermes plugin

Profile-local Hermes plugin for NAILS-002C, NAILS-002D and NAILS-002E.

**Proprietary module of the Nails project.** Not for use, copying or distribution outside this project. Plain-language documentation of every function: [docs/modules/nails-onboarding-plugin.md](../../../docs/modules/nails-onboarding-plugin.md).

## Security boundary

The model sees one tool: `nails_onboarding`.

The model can choose only:

- action;
- onboarding section when required;
- narrowly validated business payload.

The model cannot provide:

- Telegram user ID;
- chat ID;
- request ID;
- API key;
- URL;
- headers;
- arbitrary HTTP method.

The handler reads trusted task-local identity from:

```python
get_session_env("HERMES_SESSION_PLATFORM", "")
get_session_env("HERMES_SESSION_USER_ID", "")
```

It fails closed unless the platform is exactly `telegram` and the user ID is a positive integer.

## Backend access

The endpoint is fixed in code:

```text
http://127.0.0.1:8210
```

The plugin reads `NAILS_INTERNAL_API_KEY` from the profile runtime environment. The value is never returned to the model or included in logs.

Only these backend operations are mapped:

```text
start
get_state
get_master_preferences
save_master_name
save_master_style
save_default_work_hours
save_section
confirm_section
pause
resume
complete
```

Supported onboarding sections are:

```text
services
buffers
availability
bookings
```

`save_default_work_hours` stores zero or more usual daily time intervals. These intervals are reusable suggestions only. They do not create calendar availability until the master names a concrete date or period and explicitly confirms applying them.

An empty default interval list records that the master has no usual hours and plans every period separately.

`availability` contains concrete calendar dates. It supports multiple non-overlapping time intervals in one day and an explicit unavailable day. Absence of a date means unknown availability, never a free day.

There is no repeating weekly schedule action or section. `save_schedule_day` and the weekly `schedule` section were removed from the active contract.

The saved communication style controls only assistant-to-master conversation and is not inherited by client messages.

No generic HTTP client is exposed as a Hermes tool.

## Interview behavior

The Hermes skill asks one question at a time and explains why the answer matters:

- usual work hours make phrases such as “I work all next week” easy to confirm without retyping times;
- usual hours are never treated as active availability by themselves;
- service duration is needed to calculate booking end time and future free slots;
- buffers prevent appointments from being placed too close together;
- availability on specific dates prevents an empty calendar from being treated as a fully free day;
- existing appointments prevent occupied time from being offered again.

## Privacy

Master preference audit events contain only safe facts such as whether a value was set and the number of ordinary intervals. Names, free-text style details and exact work hours are not copied into audit payloads.

## Retry behavior

The plugin makes at most two attempts using the same runtime-generated request ID. A retry is allowed only for:

- transport failures;
- HTTP 502;
- HTTP 503;
- HTTP 504.

The onboarding backend operations are state-idempotent for repeated delivery.

## Error behavior

- backend `401` and `403` both become `access_denied`;
- no distinction is exposed between unknown and inactive users;
- invalid preference and action/section arguments are rejected before any network request;
- backend validation/domain errors return only safe code/details;
- response bodies from unexpected backend errors are not exposed;
- secrets and trusted identity are not included in tool results.

## Production installation target

```text
/root/.hermes/profiles/nails/plugins/nails_onboarding
```

The plugin must be enabled only for profile `nails`, and the Telegram toolset must add only:

```text
nails_onboarding
```

Existing safe toolsets remain unchanged. Universal HTTP, terminal, files, browser, code execution, MCP and infrastructure tools remain disabled.
