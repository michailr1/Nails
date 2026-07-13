# nails-scheduling

Restricted Hermes plugin for the Nails Telegram profile.

It exposes one toolset and one tool:

```text
nails_scheduling
```

Supported actions:

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

The plugin is the operational interface after onboarding. Onboarding performs initial data entry only; ordinary service and calendar changes never require restarting it.

Service management supports:

- exact lookup including archived services;
- creation with safe repeat detection;
- rename, description, price, currency, duration and buffer changes;
- archive/reactivation through `is_active`;
- full before/after confirmation in the skill contract;
- name-conflict rejection;
- no physical deletion, preserving booking history.

Price, duration and buffer changes affect future bookings. Existing bookings retain their stored commercial and timing snapshots. Renaming updates the current catalog name shown for linked bookings.

The plugin uses only fixed loopback scheduling API endpoints. Telegram identity comes from trusted Hermes session context. The model cannot supply identity, endpoint, headers, secrets, technical object identifiers, or booking idempotency data.

Client creation requires `confirmed=true` and performs an exact lookup before POST. Service writes, availability changes and booking creation also require `confirmed=true`. Booking creation rechecks the exact client, resolves timezone and the slot grid from backend data, and creates only an exact free-slot start. Runtime generates a deterministic owner-scoped idempotency key. Results remove backend object IDs before they are returned to the model.

Required environment variable:

```text
NAILS_INTERNAL_API_KEY
```
