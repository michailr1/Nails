# NAILS-002F — client matching and booking management

Issue: #59

## Scope

- candidate client lookup for diminutive names before card creation;
- explicit disambiguation instead of automatic client selection;
- owner-scoped booking reschedule;
- soft, auditable booking cancellation;
- exact free-slot validation before reschedule;
- immutable commercial and timing snapshots during reschedule;
- restricted Telegram actions with explicit confirmation;
- one compact progress message per continuous tool group.

## Runtime impact

- backend API rebuild required;
- `nails-scheduling` plugin and skill update to `0.4.0`;
- no Alembic migration; expected revision remains `0006`;
- database data changes only through confirmed user operations after deployment.

## Acceptance

Run every read-back check after `/new` so the model cannot answer from chat history.
