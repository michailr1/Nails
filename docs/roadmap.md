# Roadmap

Дата актуализации: **13 июля 2026 года**.

План построен вертикальными срезами. Каждый срез заканчивается проверяемой функцией.

## Статусы

- ✅ завершено и подтверждено в production;
- 🧪 установлено, остался acceptance test;
- 🟡 частично выполнено;
- ▶️ следующий активный срез;
- ⬜ запланировано.

## Текущая точка

```text
NAILS-001  🟡 базовые правила согласованы
NAILS-002A ✅ backend foundation production
NAILS-002B ✅ onboarding API production
NAILS-002C 🧪 restricted Hermes tool установлен, Telegram acceptance впереди
NAILS-002D ▶️ production onboarding skill
NAILS-002E ⬜ scheduling happy path
NAILS-002F ⬜ automated backup and verified restore
```

Production:

```text
host: de.funti.cc
repository HEAD: ae761e5042e2af4685df7bdb1de9485e96bdac74
backend runtime: 40b25ff5fe519eda8602d0eeac7d06a1b191138d
Hermes plugin runtime: d8264266256f6fc2c53b6eebd3b9bb6bbc722f7c
Alembic: 0002 (head)
```

Подробности:

- [`status.md`](status.md)
- [`onboarding-api.md`](onboarding-api.md)
- [`hermes-onboarding-plugin.md`](hermes-onboarding-plugin.md)
- [`deployments/2026-07-13-nails-002b.md`](deployments/2026-07-13-nails-002b.md)
- [`deployments/2026-07-13-nails-002c.md`](deployments/2026-07-13-nails-002c.md)

## NAILS-001 — процессы и правила 🟡

Зафиксированы:

- роли `master` и `admin`;
- PostgreSQL как источник истины;
- разделение public/internal data;
- snapshot стоимости;
- обязательный IANA timezone;
- confirmations;
- backup/restore как условие пилота;
- Google Calendar как optional one-way export;
- запрет shell and direct SQL for Hermes.

Финальный checklist закрывается после первого полного end-to-end onboarding.

## NAILS-002 — сквозной happy path

Цель: мастер проходит возобновляемое интервью, создаёт минимальные данные, спрашивает окна, создаёт тестовую запись и видит день.

### NAILS-002A — backend foundation ✅

В production:

- Python 3.12 + FastAPI;
- SQLAlchemy 2 + Alembic;
- PostgreSQL 17;
- Pydantic Settings;
- Ruff and pytest;
- Docker Compose;
- `/health`, `/ready`;
- owner scoping;
- restricted PostgreSQL role `nails_app`;
- clean/repeated migration CI;
- production-like Compose smoke-test.

Issue #3 closed.

### NAILS-002B — onboarding API ✅

В production:

- internal authentication boundary;
- active user and `master/admin` role checks;
- start/get/pause/resume/complete;
- drafts: schedule, services, buffers, bookings;
- separate draft and confirmed payload;
- revisions;
- ordered confirmations;
- downstream invalidation;
- idempotent confirmation/completion;
- safe audit;
- migration `0002`;
- restart persistence.

Production smoke confirmed authorization, revision behavior, pause/resume, idempotency, audit privacy and cleanup.

Issue #4 closed.

### NAILS-002C — restricted Hermes onboarding tool 🧪

Installed in production:

- profile-local plugin `nails-onboarding` version `0.1.0`;
- dedicated toolset `nails_onboarding`;
- Telegram ID only from trusted task-local gateway context;
- identity absent from model-visible arguments;
- fixed loopback API URL;
- no generic HTTP or arbitrary headers;
- safe mapping of authorization/domain errors;
- limited retry with runtime request ID;
- profile-local secret configuration;
- updated SOUL distinguishing draft, confirmed onboarding block and active working data;
- exact Telegram whitelist:
  - `clarify`;
  - `image_gen`;
  - `nails_onboarding`;
  - `skills`;
  - `tts`;
  - `vision`.

Production synthetic smoke confirmed:

- plugin discovery and load;
- identity spoofing rejection;
- non-Telegram fail-closed;
- unknown/inactive no-disclosure behavior;
- two-user owner isolation;
- backend loopback access;
- cleanup `0|0|0`;
- no side effects on Docker, backend, Amnezia or default Hermes profile.

Remaining acceptance before issue #5 closes:

- real account A starts/pause/resume through Telegram;
- real account B starts separately and cannot see A state;
- gateway restart between pause and resume;
- text attempt to request another user's state cannot alter trusted identity;
- final log privacy check.

### NAILS-002D — production skill `nails-onboarding` ▶️

Already available:

- profile SOUL;
- restricted production tool;
- honest separation of draft/confirmed/active data;
- API-backed pause/resume.

Next implementation:

- friendly introduction and capability explanation;
- explicit consent before starting interview;
- flow schedule → services → buffers → bookings;
- one clear question at a time;
- short resumable sessions;
- summaries before confirmation;
- correction and reconfirmation UX;
- handling of safe domain errors;
- completion summary that does not claim working schedule activation;
- protected feedback flow.

### NAILS-002E — scheduling happy path ⬜

- materialize confirmed onboarding blocks;
- minimal client card;
- normalized-name search;
- availability calculation;
- overlap prevention;
- booking with price snapshot;
- compact day view;
- restricted scheduling tools;
- control queries «что у меня в четверг?» and «какие окна завтра?».

### NAILS-002F — backup and restore ⬜

- scheduled PostgreSQL backups;
- copy outside active DB and single VPS disk;
- failure logging/alerting;
- restore into separate database;
- documented restore result;
- no real-data pilot before successful restore-test.

### Контрольная точка NAILS-002

NAILS-002 завершён, когда:

- full onboarding runs through Telegram role `admin`;
- state survives Hermes/backend restart;
- identity spoofing blocked;
- users isolated by owner;
- confirmed blocks materialized;
- scheduling uses materialized data;
- overlap blocked by backend;
- Hermes has no shell, SSH, direct SQL or arbitrary HTTP;
- backup restored successfully;
- synthetic data removed.

## NAILS-003 — управление записями ⬜

- transfer and cancellation;
- time blocks;
- confirmations;
- idempotency;
- delay conflict display;
- week/period views;
- feedback retention/deletion.

## NAILS-004 — расширенная клиентская база ⬜

- internal aliases and notes;
- exact/fuzzy search;
- typo and duplicate warning;
- separate public-name confirmation;
- client service overrides;
- personal duration/price;
- automatic duplicate merge prohibited.

## NAILS-005 — повседневные сценарии ⬜

- «как обычно»;
- no-show;
- morning summary;
- visit completion;
- actual final price;
- revenue reports;
- pilot metrics.

## NAILS-006 — Google Calendar ⬜

- separate calendar and credentials;
- one-way export;
- retries/backoff;
- reconciliation;
- calendar failure isolation.

## NAILS-007 — расширенное тестирование ⬜

- double booking;
- occupied transfer;
- ambiguous names;
- public/internal name isolation;
- role and owner isolation;
- day boundary and DST;
- historical price invariance;
- no-show/delay cases;
- feedback expiry;
- calendar failure isolation;
- verified restore.

## NAILS-008 — пилот ⬜

- parallel old/new schedule;
- reconciliation;
- feedback review;
- pilot metrics;
- duration corrections;
- backup monitoring;
- transition only after explicit master trust.

## После MVP

- separate public client bot;
- self-booking with master confirmation;
- separate abuse protection;
- administrative duplicate merge;
- multi-master subscription and tenant management.

## Ближайший порядок

1. Real Telegram acceptance for NAILS-002C and close issue #5.
2. NAILS-002D — production onboarding skill.
3. NAILS-002E — materialization and scheduling happy path.
4. NAILS-002F — automated backup and verified restore.
5. Full synthetic end-to-end test and cleanup.
6. Limited master pilot.
