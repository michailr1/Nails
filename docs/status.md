# Фактическое состояние проекта

Дата актуализации: **13 июля 2026 года**.

Документ разделяет состояние production, Hermes-интеграции и следующих срезов.

## 1. Сводка

| Область | Состояние |
|---|---|
| Бизнес-правила MVP | базово согласованы, NAILS-001 ещё открыт |
| Hermes Telegram Gateway | production, работает |
| Профиль `nails` | production, безопасный whitelist tools |
| Backend foundation | NAILS-002A production |
| Onboarding API | NAILS-002B production, проверен synthetic smoke |
| Production migration | `0002 (head)` |
| Hermes → Onboarding API | не подключён, активный NAILS-002C |
| Scheduling happy path | не реализован |
| Backup/restore-test | автоматизация и restore-test не реализованы |
| Пилот с мастером | не начат |

## 2. Production

VPS:

```text
de.funti.cc
```

Repository:

```text
/opt/nails/repo
```

Production environment:

```text
/opt/nails/.env
```

Production commit:

```text
40b25ff5fe519eda8602d0eeac7d06a1b191138d
```

Containers:

```text
nails-api — running, healthy
nails-db  — running, healthy
```

API:

```text
127.0.0.1:8210
GET /health → {"status":"ok"}
GET /ready  → {"status":"ready"}
```

PostgreSQL:

- Alembic `0002 (head)`;
- PostgreSQL не публикует host port;
- API подключается как `nails_app`;
- role flags: `0|0|0|0` для SUPERUSER/CREATEDB/CREATEROLE/REPLICATION;
- `nails_admin` используется только для bootstrap и controlled administration.

API container:

- user `nails`;
- read-only root filesystem;
- `CapDrop=["ALL"]`;
- `no-new-privileges:true`;
- bind только на loopback.

Production authentication setting:

- создан отдельно на VPS;
- хранится в `/opt/nails/.env`;
- файл `600 root:root`;
- значение не выводилось и не хранится в GitHub.

## 3. Production deployment NAILS-002B

Deployment выполнен с commit:

```text
40b25ff5fe519eda8602d0eeac7d06a1b191138d
```

Перед migration создан backup:

```text
/opt/nails/backups/nails_before_0002_20260712T224019Z.dump
```

Проверка `pg_restore --list` успешна.

Подтверждено:

- fast-forward `main` и чистое рабочее дерево;
- migration `0001 → 0002`;
- repeated `alembic upgrade head` без изменений;
- наличие `confirmed_payload`, `confirmed_revision`, `revision`;
- `/health` и `/ready`;
- restricted DB role и API identity;
- loopback-only API и отсутствие DB host port;
- container hardening;
- Docker daemon не перезапускался;
- Amnezia container IDs и `StartedAt` не изменились;
- Hermes, Telegram, Nginx/Traefik и другие проекты не изменялись.

Полный deployment record: [`deployments/2026-07-13-nails-002b.md`](deployments/2026-07-13-nails-002b.md).

## 4. Onboarding API в production

Endpoints:

```text
POST /api/v1/onboarding/start
GET  /api/v1/onboarding
PUT  /api/v1/onboarding/sections/{section}
POST /api/v1/onboarding/sections/{section}/confirm
POST /api/v1/onboarding/pause
POST /api/v1/onboarding/resume
POST /api/v1/onboarding/complete
```

Sections:

```text
schedule
services
buffers
bookings
```

Поддерживается:

- active user and role checks;
- draft/confirmed separation;
- revision and confirmed revision;
- ordered confirmation;
- downstream invalidation;
- idempotent confirmation/completion;
- pause/resume;
- persistence after API restart;
- safe audit metadata;
- JSON-safe validation errors without echoing source payload.

## 5. Production synthetic smoke

Проверки завершились результатом:

```text
NAILS_002B_SMOKE_OK
```

Подтверждено:

- missing/wrong authentication → `401`;
- unknown/inactive synthetic user → `403`;
- active synthetic admin starts onboarding;
- invalid schedule → `422 invalid_onboarding_payload`;
- services before schedule confirmation → `409 prior_sections_not_confirmed`;
- schedule revision 1 confirmation idempotent;
- revision 2 preserves previous effective payload until confirmation;
- services/buffers/bookings flow works;
- unknown service reference → `409 unknown_service_reference`;
- pause survives restart of only `nails-api`;
- resume works;
- completion is idempotent;
- schedule revision 1 confirmation audit count = `1`;
- completion audit count = `1`;
- audit privacy leak count = `0`;
- cleanup result = `0|0|0`;
- temporary test script removed.

## 6. Hermes production

Profile:

```text
nails
```

Allowed Telegram tools:

```text
vision
image_gen
tts
skills
clarify
```

Disabled:

```text
terminal
file
code_execution
web
browser
memory
session_search
delegation
cronjob
computer_use
context_engine
todo
kanban
MCP
GitHub
SSH
deploy tools
```

Built-in memory/user profile отключены. Persistent business state должен поступать только из PostgreSQL через restricted domain tools.

`skills.write_approval=true`.

## 7. Активный этап NAILS-002C

Issue #5 обновлена под фактическое состояние production.

Нужно:

- один restricted onboarding domain tool;
- Telegram ID только из trusted gateway context;
- отсутствие identity argument в model-visible schema;
- только start/get/save/confirm/pause/resume/complete;
- отсутствие generic HTTP, arbitrary URL/headers, SQL и filesystem;
- runtime-generated request ID;
- безопасное отображение backend errors;
- owner isolation для двух synthetic users;
- безопасный отказ unknown/inactive user;
- работа после restart Hermes;
- отсутствие authentication setting и bot token в model-visible data и logs.

## 8. Что пока не реализовано

- Hermes onboarding domain tool;
- production onboarding skill;
- automatic user provisioning;
- materialization confirmed blocks into working services/schedule/bookings;
- availability search;
- booking creation/transfer/cancellation;
- automated backups and off-host/off-disk copy;
- verified restore;
- Google Calendar.

## 9. Следующие шаги

1. Реализовать NAILS-002C через GitHub PR и CI.
2. Развернуть restricted domain tool без расширения Hermes toolsets.
3. Выполнить two-user isolation and identity spoofing tests.
4. Реализовать NAILS-002D production onboarding skill.
5. Реализовать NAILS-002E materialization and scheduling happy path.
6. Реализовать NAILS-002F automated backup and verified restore.
7. Выполнить full synthetic end-to-end test и cleanup.
8. Только после этого приглашать мастера в limited pilot.

## 10. Процесс изменений

- code, migrations, tests and docs меняются через GitHub;
- CI обязателен;
- VPS-agent deploys only an exact `main` commit;
- VPS-agent does not edit tracked files and does not push;
- production errors возвращаются в разработку как диагностика.
