# nails-scheduling

Restricted Hermes plugin for the Nails Telegram profile.

It exposes one toolset and one tool:

```text
nails_scheduling
```

Supported actions:

```text
list_services
day_view
free_slots
find_client
create_client
create_booking
```

The plugin uses only fixed loopback Booking API endpoints. Telegram identity comes from trusted Hermes session context. The model cannot supply identity, endpoint, headers, secrets, technical object identifiers, or booking idempotency data.

Client creation requires `confirmed=true` and performs its own exact lookup before POST. Booking creation requires `confirmed=true`, rechecks the exact client, resolves timezone and the slot grid from the backend, and only creates a new booking for an exact backend free-slot start. Runtime generates a deterministic owner-scoped idempotency key. Results remove backend object IDs before they are returned to the model.

Required environment variable:

```text
NAILS_INTERNAL_API_KEY
```
