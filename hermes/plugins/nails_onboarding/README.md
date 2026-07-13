# Nails onboarding Hermes plugin

Profile-local Hermes plugin for NAILS-002C and NAILS-002D.

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
save_schedule_day
save_section
confirm_section
pause
resume
complete
```

`get_master_preferences`, `save_master_name` and `save_master_style` support a short acquaintance before the business questionnaire. The saved style controls only assistant-to-master conversation and is not inherited by client messages.

`save_schedule_day` accepts one naturally collected weekday, loads the current schedule draft, merges or replaces that weekday and saves the combined draft. The model does not have to construct the whole weekly payload and cannot accidentally erase earlier days by saving the next answer.

No generic HTTP client is exposed as a Hermes tool.

## Privacy

Master preference audit events contain only safe facts such as whether a name or optional style detail was set. The preferred name and free-text style description are not copied into audit payloads.

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
- invalid preference and single-day schedule arguments are rejected before any network request;
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
