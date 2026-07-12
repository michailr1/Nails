# Roadmap

Дата актуализации: **13 июля 2026 года**.

План построен вертикальными срезами. Каждый срез заканчивается проверяемой функцией, а не только внутренними компонентами.

## Статусы

- ✅ код, тесты и CI завершены;
- 🚀 ожидает или проходит production deployment;
- 🟡 частично выполнено;
- ▶️ следующий активный срез;
- ⬜ запланировано.

## Текущая точка

```text
NAILS-001  🟡 базовые правила согласованы
NAILS-002A ✅ production foundation
NAILS-002B 🚀 onboarding API: код и CI готовы, deployment впереди
NAILS-002C ▶️ restricted Hermes domain tool
NAILS-002D 🟡 SOUL готов, production onboarding skill впереди
NAILS-002E ⬜ scheduling happy path
NAILS-002F ⬜ backup и restore-test
```

Production на `de.funti.cc` пока работает на migration `0001`. После deployment NAILS-002B ожидается migration `0002`.

Подробное состояние: [`status.md`](status.md). Контракт API: [`onboarding-api.md`](onboarding-api.md).

## NAILS-001 — процессы и правила 🟡

Уже зафиксированы:

- роли `master` и `admin`;
- PostgreSQL как источник истины;
- разделение public/internal data;
- snapshot стоимости;
- обязательный IANA timezone;
- confirmations;
- backup/restore как условие пилота;
- Google Calendar как необязательный one-way export;
- запрет shell и direct SQL для Hermes.

Остаётся закрыть финальный checklist issue #1 после первого рабочего end-to-end onboarding.

## NAILS-002 — сквозной happy path

Цель: мастер знакомится с ботом, проходит возобновляемое интервью, создаёт минимального клиента, спрашивает окна, создаёт тестовую запись и видит день.

### NAILS-002A — backend foundation ✅

Завершено и развёрнуто:

- Python 3.12 + FastAPI;
- SQLAlchemy 2 + Alembic;
- PostgreSQL 17;
- Pydantic Settings;
- Ruff и pytest;
- обязательный `APP_TIMEZONE`;
- Docker Compose;
- `/health`, `/ready`;
- migration `0001`;
- initial business and onboarding tables;
- owner scoping;
- ограниченная PostgreSQL-role `nails_app`;
- clean/repeated migration CI;
- production-like Compose smoke-test.

Issue #3 закрыта.

### NAILS-002B — onboarding API 🚀

Код и CI завершены в PR #11. Production deployment выполняется отдельно.

Реализовано:

- обязательный `INTERNAL_API_KEY`;
- trusted Telegram identity headers для будущего domain tool;
- проверка active user и роли `master/admin`;
- `start`, `get`, `pause`, `resume`, `complete`;
- draft blocks: schedule, services, buffers, bookings;
- отдельные draft и confirmed payload;
- revision and confirmed revision;
- исправление без подмены последней подтверждённой версии;
- ordered confirmation;
- downstream invalidation при изменении upstream data;
- идемпотентные повторные confirmations and completion;
- безопасный audit без полного payload;
- JSON-safe validation errors;
- migration `0002`;
- PostgreSQL integration tests;
- Compose test восстановления paused state после API restart.

Граница среза: confirmed onboarding blocks пока не материализуются в рабочие `services`, `schedule_rules`, `clients` и `bookings`. Это делается в следующих срезах.

### NAILS-002C — Hermes Gateway и restricted domain tool ▶️

Уже готово:

- отдельный bot token;
- профиль `nails`;
- allowlist;
- раздельные user sessions;
- SOUL;
- tool whitelist: `vision`, `image_gen`, `tts`, `skills`, `clarify`;
- отключены terminal, files, code execution, web/browser, cron, delegation, MCP и infrastructure tools;
- built-in memory/user profile отключены;
- `skills.write_approval=true`.

Следующий объём:

- создать узкий onboarding domain tool;
- internal API key не показывать модели;
- Telegram ID брать только из gateway context;
- не позволять модели передавать произвольный identity;
- подключить только endpoints NAILS-002B;
- negative tests для unknown/inactive users и неверного key;
- не раскрывать существование данных запрещённому пользователю;
- подтвердить разделение sessions and owners.

### NAILS-002D — skill `nails-onboarding` 🟡

Уже готово:

- профильный SOUL;
- честное разделение тестового и рабочего режима;
- запрет заявлять о сохранении без успешного API response.

Остаётся:

- production skill `nails-onboarding`;
- знакомство и ответы на вопросы;
- flow: schedule → services → buffers → bookings;
- короткие sessions;
- summary and confirmation каждого блока;
- pause/resume UX;
- capability flags;
- protected feedback flow.

### NAILS-002E — scheduling happy path ⬜

- материализация confirmed onboarding blocks;
- минимальная client card;
- exact normalized-name search;
- availability calculation;
- overlap prevention;
- booking with price snapshot;
- compact day view;
- restricted `nails-scheduling` tools;
- контрольные запросы «что у меня в четверг?» и «какие окна завтра?».

### NAILS-002F — backup и восстановление ⬜

- automatic PostgreSQL backups;
- copy outside active DB and single VPS disk;
- result log and failure alert;
- restore into separate database;
- documented restore result;
- no real-data pilot without successful restore-test.

### Контрольная точка NAILS-002

NAILS-002 завершён, когда:

- полный onboarding проходит через Telegram ролью `admin`;
- state переживает Hermes/backend restart;
- confirmed blocks materialized into working data;
- first scheduling queries use those data;
- overlap is blocked by backend;
- roles and owner checks enforced;
- Hermes still has no shell, SSH, direct SQL or arbitrary HTTP;
- backup restored successfully;
- synthetic data removed.

## NAILS-003 — управление записями ⬜

- transfer and cancellation;
- time blocks;
- confirmations;
- idempotency;
- delay conflict display without automatic day shift;
- week/period views;
- feedback retention/deletion.

## NAILS-004 — расширенная клиентская база ⬜

- internal aliases and notes;
- exact/fuzzy search;
- typo and duplicate warning;
- separate public-name confirmation;
- `client_service_overrides`;
- personal duration/price;
- automatic duplicate merge remains forbidden.

## NAILS-005 — повседневные сценарии ⬜

- «как обычно»;
- `no_show`;
- morning summary;
- visit completion;
- actual final price;
- day/week revenue;
- pilot metrics.

## NAILS-006 — Google Calendar ⬜

- separate calendar and credentials;
- `calendar_sync_jobs`;
- one-way export;
- retries/backoff;
- reconciliation;
- calendar failure never blocks business transaction.

## NAILS-007 — расширенное тестирование ⬜

- double booking;
- occupied transfer;
- ambiguous names;
- public/internal name isolation;
- repeated confirmation;
- role and owner isolation;
- day boundary and DST;
- historical price invariance;
- no-show and delays;
- feedback expiry;
- calendar failure isolation;
- verified restore.

## NAILS-008 — пилот ⬜

- parallel old/new schedule;
- reconciliation;
- feedback review;
- pilot metrics;
- service duration corrections;
- backup monitoring;
- full transition only after explicit master trust.

## После MVP

- отдельный public client bot;
- самостоятельная запись клиенток;
- master confirmation;
- separate isolation and abuse protection;
- administrative duplicate merge;
- multi-master subscription and tenant management.

## Ближайший порядок

1. Production deployment NAILS-002B.
2. NAILS-002C — restricted Hermes onboarding tool.
3. NAILS-002D — production onboarding skill.
4. NAILS-002E — scheduling happy path.
5. NAILS-002F — backup/restore.
6. Full synthetic end-to-end test and cleanup.
7. Limited master pilot.
