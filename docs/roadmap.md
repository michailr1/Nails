# Roadmap

Дата актуализации: **13 июля 2026 года**.

План построен вертикальными срезами. Каждый срез заканчивается проверяемой функцией.

## Статусы

- ✅ завершено и подтверждено в production;
- 🟡 частично выполнено;
- ▶️ следующий активный срез;
- ⬜ запланировано.

## Текущая точка

```text
NAILS-001  🟡 базовые правила согласованы
NAILS-002A ✅ backend foundation production
NAILS-002B ✅ onboarding API production
NAILS-002C ▶️ restricted Hermes onboarding tool
NAILS-002D 🟡 SOUL готов, production onboarding skill впереди
NAILS-002E ⬜ scheduling happy path
NAILS-002F ⬜ automated backup and verified restore
```

Production:

```text
host: de.funti.cc
commit: 40b25ff5fe519eda8602d0eeac7d06a1b191138d
Alembic: 0002 (head)
```

Подробности: [`status.md`](status.md), [`onboarding-api.md`](onboarding-api.md), [`deployments/2026-07-13-nails-002b.md`](deployments/2026-07-13-nails-002b.md).

## NAILS-001 — процессы и правила 🟡

Зафиксированы:

- роли `master` и `admin`;
- PostgreSQL как источник истины;
- разделение public/internal data;
- snapshot стоимости;
- обязательный IANA timezone;
- confirmations;
- backup/restore как условие пилота;
- Google Calendar как необязательный one-way export;
- запрет shell и direct SQL для Hermes.

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

Issue #3 закрыта.

### NAILS-002B — onboarding API ✅

В production:

- required runtime authentication setting;
- trusted Telegram identity contract;
- active user and `master/admin` role checks;
- start/get/pause/resume/complete;
- drafts: schedule, services, buffers, bookings;
- separate draft and confirmed payload;
- revision and confirmed revision;
- ordered confirmations;
- downstream invalidation;
- idempotent confirmations and completion;
- safe audit;
- JSON-safe validation errors;
- migration `0002`;
- PostgreSQL integration tests;
- API restart persistence.

Production smoke подтвердил authorization, draft/effective separation, correction revisions, pause/restart/resume, idempotency, audit privacy и cleanup.

Issue #4 закрыта.

### NAILS-002C — restricted Hermes onboarding tool ▶️

Уже готово:

- отдельный Telegram bot and profile `nails`;
- allowlist and separate sessions;
- SOUL;
- whitelist: `vision`, `image_gen`, `tts`, `skills`, `clarify`;
- terminal/files/code execution/web/browser/cron/delegation/MCP отключены;
- built-in memory/user profile отключены;
- `skills.write_approval=true`;
- onboarding API доступен на production loopback.

Активный объём:

- создать один узкий onboarding domain tool;
- Telegram ID брать только из trusted gateway context;
- не включать identity в model-visible arguments;
- разрешить только start/get/save/confirm/pause/resume/complete;
- не выдавать generic HTTP, arbitrary URL/headers, SQL или filesystem;
- runtime-generated request ID;
- безопасные domain errors;
- test two-user owner isolation;
- test identity spoofing resistance;
- test unknown/inactive user no-disclosure behavior;
- test restart Hermes;
- verify no token/authentication value in GitHub, logs or responses;
- aiogram не использовать.

### NAILS-002D — skill `nails-onboarding` 🟡

Уже готово:

- profile SOUL;
- честное разделение тестового/рабочего режима;
- запрет заявлять о сохранении без API success.

Остаётся:

- production skill;
- flow schedule → services → buffers → bookings;
- short resumable sessions;
- summary and confirmation каждого блока;
- pause/resume UX;
- capability flags;
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
- контрольные запросы «что у меня в четверг?» и «какие окна завтра?».

### NAILS-002F — backup and restore ⬜

- scheduled PostgreSQL backups;
- copy outside active DB and single VPS disk;
- failure logging/alerting;
- restore into separate database;
- documented restore result;
- no real-data pilot before successful restore-test.

### Контрольная точка NAILS-002

NAILS-002 завершён, когда:

- full onboarding проходит через Telegram ролью `admin`;
- state переживает Hermes/backend restart;
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

1. NAILS-002C — restricted Hermes onboarding tool.
2. NAILS-002D — production onboarding skill.
3. NAILS-002E — materialization and scheduling happy path.
4. NAILS-002F — automated backup and verified restore.
5. Full synthetic end-to-end test and cleanup.
6. Limited master pilot.
