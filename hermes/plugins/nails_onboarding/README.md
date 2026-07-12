# Nails onboarding Hermes plugin

Profile-local Hermes plugin for NAILS-002C.

## Security boundary

The model sees one tool: `nails_onboarding`.

The model can choose only:

- action;
- onboarding section when required;
- section payload when saving a draft.

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
save_section
confirm_section
pause
resume
complete
```

No generic HTTP client is exposed as a Hermes tool.

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
