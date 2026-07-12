# ADR-002: стек, Telegram-контур и развёртывание

- Статус: принято, дополнено после production deployment
- Дата принятия: 2026-07-12
- Дата дополнения: 2026-07-13

## Контекст

На VPS уже развёрнут Hermes и используется его встроенный Telegram Gateway. Отдельный Telegram framework создал бы лишний транспортный слой, дублирование sessions и allowlist, а также риск конкуренции за updates одного bot token.

Проекту нужен отдельный backend, который хранит данные и применяет бизнес-правила независимо от LLM.

После первичной настройки также подтвердилось:

- Hermes profile сам по себе не является OS sandbox;
- встроенная profile memory не подходит для бизнес-данных нескольких Telegram users;
- production backend должен быть изолирован от других сервисов VPS;
- application database role должна быть отделена от bootstrap database role.

## Решение

### Telegram и Hermes

- Telegram transport — встроенный Hermes Telegram Gateway;
- отдельный aiogram process не используется;
- Nails использует отдельный Telegram bot token;
- создаётся отдельный profile `nails`;
- profile имеет отдельные config, allowlist, SOUL и user sessions;
- built-in persistent memory и user profile отключены;
- постоянное onboarding/business state хранится только в PostgreSQL;
- Telegram ID берётся из trusted gateway/tool context, а не из текста сообщения;
- окончательная role `master` или `admin` определяется Booking API.

### Hermes tools

До подключения Booking API разрешены только:

```text
vision
image_gen
tts
skills
clarify
```

Запрещены:

- shell/terminal;
- SSH;
- arbitrary file access;
- code execution;
- direct SQL;
- web/browser/arbitrary HTTP;
- cron and delegation;
- MCP and infrastructure tools;
- credentials других профилей.

`skills.write_approval=true`.

После реализации domain API profile получает только узкие Nails tools. Универсальный HTTP client не выдаётся.

### Backend

Принят стек:

- Python 3.12;
- FastAPI;
- PostgreSQL;
- SQLAlchemy 2;
- Alembic;
- Pydantic Settings;
- pytest;
- Ruff.

Booking API является единственной точкой чтения и записи бизнес-данных и единственным компонентом, который применяет роли, owner checks, validations, confirmations, idempotency и audit.

### Развёртывание

Production размещён на том же VPS, где работает Hermes, но в отдельном контуре:

```text
Hermes
└── profile: nails
    ├── separate bot token
    ├── separate allowlist
    ├── separate user sessions
    ├── SOUL.md
    └── restricted tools

/opt/nails/
├── repo
├── .env outside repository
└── Docker Compose
    ├── nails-api
    └── nails-db
```

Production host:

```text
de.funti.cc
```

API bind:

```text
127.0.0.1:8210
```

PostgreSQL не публикует host port.

### Docker networks

```text
nails-api
├── nails-edge
└── nails-internal
          ↓
       nails-db
```

- DB connected only to internal network;
- API connected to internal and edge networks;
- edge port bound only to loopback.

### Database roles

- `nails_admin` — bootstrap role контейнера PostgreSQL;
- `nails_app` — application role Booking API.

`nails_app` создаётся без:

- `SUPERUSER`;
- `CREATEDB`;
- `CREATEROLE`;
- `REPLICATION`.

API не использует bootstrap credentials.

### Application container hardening

- non-root user `nails`;
- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges:true`.

### Timezone

- `APP_TIMEZONE` обязателен;
- только IANA timezone;
- invalid/empty value blocks startup;
- production value: `Europe/Berlin`.

### Backups

Backup и verified restore обязательны до real-data pilot. Volume persistence across restart не считается backup.

## Текущий результат

NAILS-002A развёрнут в production:

```text
commit cca0109ea8c716fdf03d97c34a1c0f06bfb5fc50
migration 0001 (head)
```

Проверены:

- clean migration;
- repeated migration;
- Compose startup;
- restricted DB role;
- API current_user;
- loopback health/readiness;
- persistence after restart;
- container hardening.

Hermes и backend пока не связаны domain tools. Это следующий архитектурный шаг после onboarding API.

## Кнопки Telegram

На первом рабочем этапе допускаются обычный текст и structured clarify options. Реализация не должна зависеть от custom inline callbacks.

Отдельный aiogram layer рассматривается только при доказанной невозможности реализовать обязательный UX через Hermes Gateway и потребует отдельного ADR.

## Последствия

### Преимущества

- единый Telegram transport;
- нет конкуренции за bot token;
- бизнес-данные не зависят от LLM memory;
- model permissions ограничены технически;
- database credentials and roles separated;
- backend and DB isolated from external network;
- deployment воспроизводится через GitHub/CI/Compose.

### Ограничения

- Telegram UI зависит от Hermes Gateway;
- onboarding/scheduling требуют отдельных domain tools;
- built-in Hermes memory нельзя использовать как CRM storage;
- API пока local-only;
- pilot невозможен до backup/restore and end-to-end testing.

## Отклонённые варианты

### Отдельный aiogram bot для MVP

Отклонён из-за дублирования Telegram transport, sessions and allowlist.

### Direct SQL from Hermes

Отклонён: невозможно надёжно ограничить business invariants and tenant scope at prompt level.

### Universal HTTP tool

Отклонён: profile должен видеть только whitelisted domain operations.

### Persistent business state in Hermes memory

Отклонён: memory is not tenant-aware and can mix user data.

### API under PostgreSQL bootstrap user

Отклонён из-за excessive privileges.
