# Фактическое состояние проекта

Дата актуализации: **13 июля 2026 года**.

Этот документ отделяет уже работающие компоненты от целевых функций. Описание будущих возможностей в README, roadmap и бизнес-процессах не означает, что они уже доступны в production.

## 1. Общий статус

| Область | Состояние |
|---|---|
| Бизнес-правила MVP | базово согласованы, финальный чек-лист NAILS-001 ещё открыт |
| Hermes Telegram Gateway | развёрнут и работает |
| Профиль Hermes `nails` | развёрнут, ограничен whitelist инструментов |
| Smart Nails SOUL | установлен, запрещает преувеличивать возможности |
| Backend foundation | завершён, NAILS-002A |
| PostgreSQL schema | миграция `0001 (head)` применена в production |
| Onboarding API | следующий этап, ещё не реализован |
| Hermes → Booking API | ещё не подключён |
| Scheduling happy path | ещё не реализован |
| Backup и проверка восстановления | ещё не реализованы |
| Google Calendar | запланирован на NAILS-006 |
| Пилот с мастером | ещё не начат |

## 2. Production

Production размещён только на VPS:

```text
de.funti.cc
```

Репозиторий на сервере:

```text
/opt/nails/repo
```

Production commit backend foundation:

```text
cca0109ea8c716fdf03d97c34a1c0f06bfb5fc50
```

Production environment:

```text
/opt/nails/.env
```

Файл находится вне репозитория, имеет права `600 root:root` и не должен выводиться в отчёты или CI.

### Контейнеры

- `nails-api` — running, healthy;
- `nails-db` — running, healthy.

### API

- локальный адрес: `127.0.0.1:8210`;
- `GET /health` → `{"status":"ok"}`;
- `GET /ready` → `{"status":"ready"}`;
- OpenAPI/Swagger в текущем каркасе наружу не публикуется.

### PostgreSQL

- Alembic: `0001 (head)`;
- PostgreSQL не имеет опубликованного host-порта;
- `nails-db` подключён только к `nails-internal`;
- `nails-api` подключён к `nails-internal` и `nails-edge`;
- приложение подключается как `nails_app`;
- `nails_app` не имеет `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `REPLICATION`;
- bootstrap-пользователь `nails_admin` не используется приложением.

### Защита API-контейнера

- непривилегированный пользователь `nails`;
- read-only root filesystem;
- все Linux capabilities удалены;
- `no-new-privileges:true`;
- API опубликован только на loopback.

### Проверки production

Подтверждено:

- миграция применяется на чистую базу;
- повторный `alembic upgrade head` безопасен;
- health/readiness работают;
- API подключён ограниченной ролью;
- синтетическая запись сохраняется после рестарта;
- синтетическая запись после проверки удалена;
- в последних проверенных логах нет traceback, migration error, authentication failure или цикла рестартов.

## 3. Telegram и Hermes

Работает отдельный профиль:

```text
nails
```

Он использует отдельные:

- Telegram bot token;
- allowlist;
- конфигурацию;
- SOUL;
- сессии пользователей.

### Разрешённые инструменты Telegram

```text
vision
image_gen
tts
skills
clarify
```

### Запрещённые инструменты

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

Встроенная память Hermes и user profile отключены. Причина: профиль используется несколькими Telegram-пользователями, а общая файловая память могла бы смешать их данные. Рабочее состояние мастера должно храниться в PostgreSQL и выдаваться только через Booking API.

`skills.write_approval=true`: изменение skills требует отдельного подтверждения.

### Что Smart Nails умеет сейчас

- вести обычный диалог;
- честно объяснять текущие ограничения;
- задавать структурированные уточняющие вопросы;
- анализировать изображения в рамках доступного vision tool;
- генерировать изображения;
- создавать TTS-ответы;
- использовать разрешённые skills.

### Чего Smart Nails пока не умеет

- сохранять график, услуги, клиентов и записи в backend;
- проверять реальные свободные окна;
- выполнять операции записи;
- продолжать onboarding через PostgreSQL;
- определять роль через Booking API.

## 4. Реализовано в NAILS-002A

- Python 3.12 и FastAPI;
- SQLAlchemy 2;
- Alembic;
- PostgreSQL 17;
- Pydantic Settings;
- обязательный `APP_TIMEZONE` в формате IANA;
- Ruff и pytest;
- Docker Compose deployment;
- CI с PostgreSQL service и production-подобным Compose smoke-test;
- initial schema:
  - `users`;
  - `services`;
  - `clients`;
  - `bookings`;
  - `schedule_rules`;
  - `schedule_exceptions`;
  - `audit_events`;
  - `onboarding_states`;
  - `onboarding_drafts`.

Бизнес-таблицы привязаны к владельцу через `owner_user_id`. Удаление пользователя не должно каскадно уничтожать рабочую историю. Idempotency key записи уникален в пределах владельца.

## 5. Исправленные ошибки и блокеры

### Преувеличение возможностей Smart Nails

Проблема: бот предлагал «настроить график» и создавал впечатление, что данные уже сохраняются.

Исправление: SOUL требует отличать тестовое интервью от рабочего сохранения и запрещает утверждать, что график, услуга или запись сохранены без подтверждённого результата Booking API.

### Слишком широкие Hermes toolsets

Проблема: профиль показывал административные и универсальные инструменты, потенциально опасные на VPS.

Исправление: применён точный Telegram whitelist из пяти пользовательских toolsets. Terminal, files, web, browser, code execution, cron, delegation, MCP и infrastructure tools отключены.

### Риск смешивания памяти пользователей

Проблема: встроенная файловая память Hermes является общей для профиля и не подходит для бизнес-данных нескольких пользователей.

Исправление: `memory.memory_enabled=false` и `memory.user_profile_enabled=false`. Источник истины — PostgreSQL.

### Allowlist тестового Telegram-пользователя

Проблема: разрешённый тестовый аккаунт сначала молча игнорировался gateway.

Исправление: проверены фактический Telegram ID, `.env` профиля и окружение процесса; allowlist перечитан после корректного рестарта профильного gateway.

### PostgreSQL application role

Проблема: первоначальный вариант Compose мог использовать bootstrap-пользователя PostgreSQL с избыточными правами.

Исправление: разделены `nails_admin` и ограниченный `nails_app`; CI проверяет фактические атрибуты роли и `current_user` API.

### Сетевая топология Compose

Проблема: полностью internal Docker network позволяла API общаться с БД, но блокировала loopback-доступ к API с VPS.

Исправление: `nails-db` оставлен только в `nails-internal`, а `nails-api` подключён дополнительно к `nails-edge`; порт опубликован строго на `127.0.0.1`.

### Защита от удаления бизнес-данных

Проблема: каскадное удаление владельца могло уничтожить услуги, клиентов, график и записи.

Исправление: owner foreign keys используют защитное поведение `RESTRICT`; удаление и архивирование должны выполняться отдельными бизнес-операциями.

### Scope idempotency

Проблема: глобальная уникальность idempotency key могла создавать ложные конфликты между мастерами.

Исправление: ключ уникален по паре `owner_user_id + idempotency_key`.

### Отсутствие Docker Compose на production VPS

Проблема: Ubuntu Docker Engine был установлен как `docker.io`, но Compose CLI отсутствовал.

Исправление: установлен совместимый Ubuntu-пакет `docker-compose-v2` из `noble-updates/universe`. Docker Engine, daemon и существующие Amnezia-контейнеры не перезапускались и не заменялись.

## 6. Следующие шаги

### NAILS-002B — следующий активный срез

- onboarding API;
- trusted identification пользователя;
- start/get/pause/resume/complete onboarding;
- черновики графика, услуг, буферов и записей;
- подтверждение каждого блока;
- аудит изменений;
- тест продолжения после рестарта.

### Затем

1. Завершить NAILS-002C: подключить Hermes к узким domain tools и проверке ролей Booking API.
2. Реализовать NAILS-002D: production skill `nails-onboarding`.
3. Реализовать NAILS-002E: первый scheduling happy path.
4. Реализовать NAILS-002F: автоматический backup и реальное тестовое восстановление.
5. Провести полный синтетический прогон ролью `admin`.
6. Очистить тестовые данные.
7. Подключить мастера к ограниченному пилоту.

## 7. Условия начала пилота

Пилот с реальными данными не начинается, пока не выполнены все условия:

- onboarding сохраняется в PostgreSQL;
- Hermes использует только ограниченные Booking API tools;
- роли проверяются backend;
- опасные операции подтверждаются;
- test restore backup успешно выполнен и документирован;
- исключена утечка внутренних алиасов;
- синтетические end-to-end тесты пройдены;
- тестовые данные очищены.

## 8. Процесс изменений

- основной ChatGPT изменяет код и документацию через GitHub;
- изменения проходят PR и CI;
- VPS-агент не разрабатывает и не исправляет tracked-файлы;
- VPS-агент получает точный commit из `main`, разворачивает его на `de.funti.cc` и выполняет production-проверки;
- при ошибке deployment агент останавливается и возвращает диагностику.
