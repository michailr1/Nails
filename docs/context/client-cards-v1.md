# Client cards v1

## Purpose

Client cards store information that helps the master recognise a client, prepare for a visit and communicate appropriately. They are master-owned operational records, not public client profiles.

## Fields

Existing fields remain compatible:

- `public_name` — the only name allowed in client-facing communication;
- `phone` — optional contact number;
- `profile_status` — active or archived.

Optional v1 fields:

- `private_alias` — master-only search label; never use when addressing the client;
- `contact_channel` — preferred contact channel or handle;
- `birthday` — optional calendar date without mandatory year semantics in dialogue;
- `general_notes` — private general notes;
- `nail_skin_notes` — nail, skin and recurring technical characteristics;
- `sensitivity_notes` — allergies, sensitivities and contraindication notes reported by the master;
- `style_preferences` — preferred services, shapes, lengths, colours and styles;
- `communication_preferences` — preferred tone, timing or contact conventions.

All new fields are nullable. Existing rows require no backfill values.

## Trust and privacy boundaries

- `public_name` is the only client-facing identity.
- `private_alias` and every notes field are master-only.
- private fields may be returned only through the authenticated owner-scoped scheduling API and restricted Nails tool.
- private aliases may help exact/candidate lookup but must not replace `public_name` in booking summaries or outgoing messages.
- technical IDs remain hidden from the model-facing tool result.
- audit events record changed field names and presence flags, not sensitive note contents.

## Dialogue contract

- do not require every optional field when creating a card;
- ask only for details relevant to the current request;
- show a compact `current → future` summary before an update;
- require explicit confirmation for create and update;
- perform a fresh exact lookup after every write;
- when a name may be a typo or duplicate, run exact and candidate lookup before creating a new card;
- never address a client using a private alias such as `Маша сложные ногти`.

## Visit history

Visit history is derived from bookings and is not copied into free-text client fields.

## Delivery slices

1. Database migration, model, owner-scoped API create/read/update and backend tests.
2. Restricted tool actions, sanitised presenters, dialogue skill and plugin contract tests.
