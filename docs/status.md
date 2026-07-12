# Фактическое состояние проекта

Дата актуализации: **13 июля 2026 года**.

Документ разделяет состояние кода, production и Telegram-интеграции. Наличие функции в `main` не означает, что она уже развёрнута на VPS или подключена к Hermes.

## 1. Сводка

| Область | Состояние |
|---|---|
| Бизнес-правила MVP | базово согласованы, NAILS-001 ещё открыт |
| Hermes Telegram Gateway | production, работает |
| Профиль `nails` | production, безопасный whitelist tools |
| Backend foundation | NAILS-002A production |
| Onboarding API | NAILS-002B реализован и проверяется PR/CI, deployment отдельно |
| Production migration | пока `0001 (head)` |
| Новая migration в коде | `0002` |
| Hermes → Onboarding API | не подключён, следующий NAILS-002C |
| Scheduling happy path | не реализован |
| Backup/restore-test | не реализован |
| Пилот с мастером | не начат |

## 2. Production до deployment NAILS-002B

VPS:

```text
de.funti.cc
```

Repository:

```text
/opt/nails/repo
```

Environment:

```text
/opt/nails/.env
```

Текущий production backend commit:

```text
cca0109ea8c716fdf03d97c34a1c0f06bfb5fc50
```

Контейнеры:

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

- migration `0001 (head)`;
- host port отсутствует;
- API подключается как restricted role `nails_app`;
- `nails_admin` используется только для bootstrap;
- `nails_app`: `SUPERUSER=0`, `CREATEDB=0`, `CREATEROLE=0`, `REPLICATION=0`.

API container:

- user `nails`;
- read-only root filesystem;
- `CapDrop=ALL`;
- `no-new-privileges:true`;
- bind только на loopback.

## 3. Hermes production

Профиль:

```text
nails
```

Разрешённые Telegram tools:

```text
vision
image_gen
tts
skills
clarify
```

Отключены:

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

Built-in profile memory отключена, чтобы данные разных Telegram users не смешивались. Persistent state должен поступать только из PostgreSQL через restricted domain tools.

`skills.write_approval=true`.

## 4. NAILS-002B — реализовано в коде

### Authentication boundary

- обязательный `INTERNAL_API_KEY` не короче 32 символов;
- key сравнивается constant-time;
- Telegram ID передаётся только внутренним header;
- пользователь должен существовать в `users`, быть active и иметь role `master` or `admin`;
- unknown/inactive user получает отказ;
- автоматического provisioning нет.

### Endpoints

```text
POST /api/v1/onboarding/start
GET  /api/v1/onboarding
PUT  /api/v1/onboarding/sections/{section}
POST /api/v1/onboarding/sections/{section}/confirm
POST /api/v1/onboarding/pause
POST /api/v1/onboarding/resume
POST /api/v1/onboarding/complete
```

### Sections

```text
schedule
services
buffers
bookings
```

### Draft model

Для каждого блока отдельно хранятся:

- current draft payload;
- last confirmed payload;
- current revision;
- confirmed revision;
- confirmation status/time.

Редактирование подтверждённого блока не подменяет последнюю effective version до нового подтверждения.

Повторное confirmation одной revision и повторное completion идемпотентны.

Изменение и новое подтверждение upstream section инвалидирует downstream confirmations, зависящие от старых данных.

### Validation

- schedule intervals and weekday uniqueness;
- all seven weekdays required for schedule confirmation;
- unique public service names;
- non-negative price and ISO currency;
- duration and buffer limits;
- service references in buffers/bookings;
- timezone-aware future booking input;
- JSON-safe errors without echoing original payload.

### Audit

Создаются события:

```text
onboarding.started
onboarding.draft_saved
onboarding.section_confirmed
onboarding.paused
onboarding.resumed
onboarding.completed
```

Audit содержит только safe metadata: section, revision, status and invalidated sections. Полный onboarding payload не записывается.

### Migration `0002`

Добавляет в `onboarding_drafts`:

- `confirmed_payload`;
- `revision`;
- `confirmed_revision`;
- consistency constraints.

Существующие confirmed rows при migration получают compatible confirmed snapshot.

## 5. Проверки NAILS-002B

Backend CI проверяет:

- Ruff;
- migration `0001 → 0002` на clean PostgreSQL 17;
- repeated `alembic upgrade head`;
- config and authentication;
- role access;
- pause/resume and state persistence;
- draft/effective separation;
- confirmation idempotency;
- confirmation order;
- service references;
- downstream invalidation;
- completion requirements;
- audit payload safety.

Compose smoke-test дополнительно:

- запускает production-like stack;
- проверяет restricted `nails_app`;
- проверяет `/health` and `/ready`;
- создаёт synthetic admin;
- начинает and pauses onboarding;
- restarts `nails-api`;
- подтверждает restored paused state.

## 6. Что после merge ещё не будет работать

Даже после merge и deployment NAILS-002B Smart Nails не сможет сохранять данные из Telegram, пока не выполнен NAILS-002C.

Не реализованы:

- Hermes onboarding domain tool;
- automatic user provisioning;
- materialization confirmed blocks into working services/schedule/bookings;
- availability search;
- booking creation/transfer/cancellation;
- Google Calendar;
- backup and restore.

## 7. Исправленные проблемы

- SOUL запрещает преувеличивать возможности;
- Hermes administrative tools removed;
- shared profile memory disabled;
- Telegram allowlist corrected and tested;
- PostgreSQL bootstrap/app roles separated;
- Docker internal/edge networks separated;
- owner deletion protected by `RESTRICT`;
- booking idempotency scoped by owner;
- Ubuntu `docker-compose-v2` installed without Docker restart;
- Pydantic validation errors sanitized to JSON-safe details.

## 8. Следующие шаги

1. Merge PR #11 после полностью зелёного CI.
2. Создать secure `INTERNAL_API_KEY` в `/opt/nails/.env`.
3. Back up production DB and deploy exact main commit.
4. Apply migration `0002`.
5. Выполнить synthetic API lifecycle and cleanup.
6. NAILS-002C: restricted Hermes onboarding tool.
7. NAILS-002D: production onboarding skill.
8. NAILS-002E: materialization and scheduling happy path.
9. NAILS-002F: automated backup and verified restore.

## 9. Условия пилота

Real-data pilot не начинается, пока:

- Telegram flow сохраняет onboarding через restricted tool;
- roles and owners проверяются backend;
- confirmed blocks materialized;
- scheduling end-to-end работает;
- backup successfully restored;
- internal aliases cannot leak;
- synthetic tests passed and cleaned.

## 10. Процесс изменений

- code, migrations, tests and docs изменяются через GitHub;
- CI обязателен;
- VPS-agent deploys only exact `main` commit;
- VPS-agent does not edit tracked files and does not push;
- production error возвращается разработчику как диагностика.
