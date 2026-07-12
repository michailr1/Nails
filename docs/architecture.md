# Архитектура

## 1. Назначение

Nails — закрытый Telegram-помощник мастера по ведению графика, услуг, клиентов и записей. Диалог ведёт Hermes, но все бизнес-правила и данные контролируются отдельным Booking API и PostgreSQL.

Главный принцип:

> Модель может предложить действие, но не может сама считать его выполненным.

Любое чтение или изменение рабочих данных должно происходить через ограниченную функцию Booking API с серверной проверкой роли, владельца и бизнес-правил.

## 2. Фактическое состояние на 13 июля 2026 года

```text
Telegram
   ↓
Hermes Telegram Gateway
   ↓
profile: nails
   ├── SOUL.md
   ├── separate user sessions
   └── safe tools: vision, image_gen, tts, skills, clarify

127.0.0.1:8210
   ↓
nails-api (FastAPI)
   ↓
nails-db (PostgreSQL)
```

Обе части уже работают на `de.funti.cc`, но **Hermes пока не подключён к Booking API**. Поэтому Telegram-профиль ещё не может сохранять график, услуги, клиентов и записи.

Production backend commit:

```text
cca0109ea8c716fdf03d97c34a1c0f06bfb5fc50
```

Alembic revision:

```text
0001 (head)
```

## 3. Целевая схема

```text
Telegram user
   ↓
Hermes Telegram Gateway
   ↓ trusted platform context
profile: nails
   ↓ restricted Nails domain tools
Booking API (FastAPI)
   ├── authentication by trusted Telegram identity
   ├── role and owner checks
   ├── validation and confirmation rules
   ├── audit and idempotency
   └── transactions
   ↓
PostgreSQL — source of truth
```

Google Calendar подключается позднее только как одностороннее визуальное представление подтверждённых данных.

## 4. Hermes Telegram Gateway

Gateway:

- является единственным Telegram-транспортом;
- использует отдельный bot token для Nails;
- принимает личные сообщения только от Telegram ID из allowlist;
- создаёт раздельные пользовательские сессии;
- передаёт платформенный Telegram ID через доверенный gateway context;
- не заменяется aiogram в MVP.

Allowlist отвечает только на вопрос «можно ли начать диалог». Он **не определяет бизнес-роль** и не даёт доступ к данным конкретного мастера. Роль и принадлежность данных обязан проверять Booking API.

## 5. Профиль Hermes `nails`

Профиль изолирован от основного Hermes-профиля и имеет отдельные:

- `.env`;
- конфигурацию;
- Telegram token;
- allowlist;
- SOUL;
- пользовательские сессии;
- набор разрешённых инструментов.

### Текущий whitelist

```text
vision
image_gen
tts
skills
clarify
```

### Запрещено

```text
terminal
file
code_execution
web
browser
arbitrary HTTP
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
deployment tools
direct SQL
```

`skills.write_approval=true`: агент не должен самостоятельно менять skills без подтверждения.

### Почему отключена встроенная память

Встроенные `MEMORY.md` и `USER.md` являются профильными, а не полноценной tenant-aware бизнес-базой. При нескольких Telegram-пользователях это создаёт риск смешивания данных.

Поэтому:

```text
memory.memory_enabled=false
memory.user_profile_enabled=false
```

Hermes помнит текущую сессию, но постоянное состояние графика, onboarding и клиентской базы должно храниться в PostgreSQL.

## 6. Booking API

Booking API является единственной точкой доступа к бизнес-данным.

### Уже реализовано

- FastAPI application foundation;
- обязательная runtime-конфигурация;
- IANA validation для `APP_TIMEZONE`;
- SQLAlchemy engine и sessions;
- Alembic migration framework;
- `/health`;
- `/ready` с проверкой PostgreSQL;
- initial schema;
- Docker image и Compose deployment;
- CI и production-like smoke-test.

### Следующий срез

NAILS-002B добавит:

- `start_onboarding`;
- `get_onboarding_state`;
- сохранение черновиков;
- подтверждение и исправление блоков;
- `pause_onboarding`;
- `resume_onboarding`;
- `complete_onboarding`;
- audit events;
- server-side role checks.

### Будущие обязанности

- поиск свободных интервалов;
- проверка пересечений;
- расчёт длительности и буферов;
- создание, перенос и отмена записей;
- управление клиентскими карточками;
- снимок стоимости;
- безопасный аудит;
- idempotency;
- календарные sync jobs.

## 7. PostgreSQL

PostgreSQL — единственный источник истины.

### Фактически созданные таблицы

```text
users
services
clients
bookings
schedule_rules
schedule_exceptions
audit_events
onboarding_states
onboarding_drafts
```

Основные бизнес-таблицы содержат `owner_user_id`. Это является базой tenant isolation, но само наличие поля не заменяет обязательные фильтры и проверки в API.

Удаление владельца не каскадно уничтожает рабочую историю: owner foreign keys используют защитную семантику `RESTRICT` там, где потеря данных недопустима.

Idempotency записи ограничена владельцем:

```text
owner_user_id + idempotency_key
```

### Роли PostgreSQL

- `nails_admin` — bootstrap-role контейнера, только для первичной инициализации;
- `nails_app` — application-role Booking API.

`nails_app` не имеет:

- `SUPERUSER`;
- `CREATEDB`;
- `CREATEROLE`;
- `REPLICATION`.

## 8. Docker topology

```text
VPS de.funti.cc

127.0.0.1:8210
      ↓
  nails-api
   ├── nails-edge
   └── nails-internal
             ↓
          nails-db
```

- `nails-db` подключён только к `nails-internal`;
- PostgreSQL не публикует host-port;
- `nails-api` использует `nails-internal` для БД;
- `nails-api` использует `nails-edge` для loopback HTTP;
- внешний bind API отсутствует.

Контейнер API:

- работает как непривилегированный пользователь `nails`;
- имеет read-only root filesystem;
- запускается с `CapDrop=ALL`;
- использует `no-new-privileges:true`.

## 9. Время

- `APP_TIMEZONE` обязателен;
- используется формат IANA;
- неизвестная или пустая зона блокирует запуск;
- production: `Europe/Berlin`;
- бизнес-границы дня вычисляются в зоне мастера;
- timestamps в БД хранятся timezone-aware там, где представляют момент времени.

Автоматический молчаливый fallback на UTC запрещён.

## 10. Поток onboarding

Целевой поток NAILS-002B–002D:

```text
Telegram message
  → Hermes identifies onboarding intent
  → restricted onboarding tool
  → Booking API resolves trusted Telegram identity
  → role/owner validation
  → draft saved in PostgreSQL
  → summary returned to Hermes
  → user confirms or corrects
  → confirmed block becomes available to later business logic
```

Черновые данные не должны влиять на рабочее расписание до подтверждения блока.

## 11. Поток записи

Целевой поток NAILS-002E и NAILS-003:

```text
User request
  → Hermes extracts intent and parameters
  → Booking API resolves role and owner
  → client/service lookup
  → duration, buffer and availability calculation
  → summary and confirmation
  → transactional write
       - booking change
       - audit event
       - calendar sync job after NAILS-006
  → result returned to Telegram
```

Google Calendar не участвует в бизнес-транзакции.

## 12. Google Calendar

Google Calendar подключается на NAILS-006:

- только односторонний экспорт из PostgreSQL;
- ошибка календаря не отменяет бизнес-операцию;
- используются retries и backoff;
- credentials доступны только sync-component;
- модель не получает calendar credentials.

## 13. Backup

До пилота с реальными данными обязательны:

- автоматические PostgreSQL backups;
- копия вне рабочей БД и вне единственного диска VPS;
- журнал результатов;
- тест восстановления в отдельную БД;
- документированный результат restore-test.

Запуск контейнеров и сохранение данных после restart уже проверены, но это не заменяет backup и disaster recovery.

## 14. Разделение ответственности

### GitHub / основной ChatGPT

- архитектура;
- код;
- миграции;
- тесты;
- CI;
- документация;
- PR и merge.

### VPS-агент

- проверка конкретного hostname;
- получение точного commit из `main`;
- deployment;
- миграции;
- runtime и infrastructure tests;
- отчёт об ошибках.

VPS-агент не исправляет tracked-файлы и не выполняет push.

## 15. Принципы безопасности

- профиль Hermes не считается sandbox;
- отсутствие инструмента означает отсутствие функции;
- модель не является доверенным источником Telegram ID или роли;
- все business writes проверяются backend;
- внутренние aliases не используются как public names;
- production data не попадает в GitHub и CI;
- secrets не выводятся в логи и отчёты;
- pilot начинается только после end-to-end tests и restore-test.

## 16. Будущий публичный контур

Клиентский бот не входит в MVP. Он должен быть отдельным агентом с отдельной авторизацией, отдельными tools и существенно меньшими полномочиями. Его нельзя совмещать с доверенным контуром мастера.
