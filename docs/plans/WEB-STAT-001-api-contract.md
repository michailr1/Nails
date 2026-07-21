# WEB-STAT-001 — Statistics API contract

`GET /web/api/statistics?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

Read-only owner-scoped endpoint. Maximum range: 366 local calendar days.

Response separates:

- `revenue_amount` — total known revenue from completed visits and ended `scheduled` visits;
- `confirmed_revenue_amount` — confirmed completed revenue;
- `estimated_revenue_amount` — ended but not manually confirmed visits and unconfirmed range lower bounds;
- `unknown_price_count` — visits that must not be silently represented as zero;
- `confirmed_visits_count` and `assumed_visits_count`;
- local-day series;
- procedures and add-ons by visit count using booking snapshots;
- clients by known revenue and visits.

Future appointments, cancellations and no-shows are excluded from revenue. Cancelled and no-show counts remain visible separately.