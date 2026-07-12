# Приватность и модель данных

Дата актуализации: **13 июля 2026 года**.

## 1. Основные правила

- PostgreSQL — единственный источник бизнес-данных.
- Telegram allowlist не заменяет owner and role checks.
- Реальные данные не попадают в GitHub, issues, PR, Actions logs или screenshots.
- Внутренние обозначения мастера отделяются от публичных данных клиентки.
- Draft onboarding data не участвуют в рабочем расписании до подтверждения.
- Built-in Hermes memory не используется для постоянных данных.

## 2. Классы данных

### Публично допустимые поля

Поля, которые в будущем могут использоваться в сообщении клиентке:

- `public_name`;
- публичное название услуги;
- дата и время записи;
- публичная стоимость;
- публичные правила посещения.

### Внутренние поля

Доступны только доверенному контуру `master/admin`:

- `internal_alias`;
- `internal_notes`;
- служебные теги;
- история изменений;
- technical identifiers;
- feedback context;
- показатели no-show;
- рабочие замечания.

Внутренние значения не передаются в клиентский контур, публичные templates или внешние integrations.

## 3. Фактически реализованная схема `0001`

Production migration:

```text
0001 (head)
```

Созданы таблицы:

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

### `users`

- `id` — UUID;
- `telegram_user_id` — unique bigint;
- `role` — `admin` or `master`;
- `is_active`;
- timestamps.

Telegram ID хранится как технический идентификатор. Он не должен выводиться в публичные ответы и не принимается из model-generated text как trusted value.

### Owner-scoped tables

Таблицы:

- `services`;
- `clients`;
- `bookings`;
- `schedule_rules`;
- `schedule_exceptions`;

содержат `owner_user_id`.

Это база tenant isolation. Booking API обязан добавлять owner filter ко всем операциям чтения и записи. Само наличие поля в таблице не считается достаточной авторизацией.

### `services`

Фактически предусмотрены:

- owner;
- public name and description;
- current price;
- currency;
- standard duration;
- buffer before/after;
- active flag;
- timestamps.

Название услуги уникально в пределах владельца, а не глобально для всех мастеров.

### `clients`

Фактически предусмотрены:

- owner;
- `public_name`;
- `normalized_public_name`;
- optional phone;
- profile status;
- `archived_at`;
- timestamps.

Internal aliases and notes в migration `0001` ещё не созданы. Они относятся к NAILS-004.

### `bookings`

Фактически предусмотрены:

- owner;
- client and service references;
- planned start/end;
- expected end during delay;
- actual start/end;
- status: `scheduled`, `completed`, `cancelled`, `no_show`;
- price snapshot;
- currency;
- price source;
- price confirmation/completion timestamps;
- idempotency key;
- timestamps.

Idempotency uniqueness:

```text
owner_user_id + idempotency_key
```

Изменение текущей цены услуги не должно изменять historical booking price.

### `schedule_rules`

Хранит обычный weekly schedule:

- owner;
- weekday;
- start/end local time;
- working flag;
- optional validity range;
- timestamps.

Database constraints проверяют weekday range и корректность рабочего интервала.

### `schedule_exceptions`

Хранит one-off changes:

- owner;
- date;
- optional working interval;
- working/non-working flag;
- reason;
- timestamps.

### `audit_events`

Фактически предусмотрены:

- optional owner;
- optional actor;
- action;
- object type and ID;
- request ID;
- safe JSON changes;
- creation time.

В audit запрещено сохранять secrets, credentials и полный чувствительный payload.

### `onboarding_states`

- user reference;
- status: `not_started`, `in_progress`, `paused`, `completed`;
- current step;
- start/completion timestamps;
- timestamps.

### `onboarding_drafts`

- onboarding state reference;
- section: schedule/services/buffers/bookings;
- JSONB payload;
- confirmation flag/time;
- timestamps.

Один draft section уникален в пределах onboarding state.

## 4. Что ещё не реализовано в схеме

Следующие целевые entities пока отсутствуют:

- `client_internal_aliases`;
- `client_internal_notes`;
- `client_service_overrides`;
- `feedback_events`;
- `calendar_sync_jobs`;
- отдельные pilot metrics tables, если будут нужны;
- public client identities.

Их нельзя считать доступными только потому, что они описаны в целевой модели.

## 5. Целевая расширенная модель

### `client_internal_aliases`

- `client_id`;
- private alias;
- normalized alias;
- `created_by`;
- timestamp.

Alias используется только для поиска в доверенном контуре. Он никогда не становится public name автоматически.

### `client_internal_notes`

- `client_id`;
- note;
- visibility `master_admin_only`;
- `created_by`;
- timestamps.

Свободная note не является источником duration, price or business rule.

### `client_service_overrides`

Структурированные корректировки пары client/service:

- duration adjustment;
- optional personal price/rule;
- creator;
- timestamps.

Используется вместо извлечения правил из notes.

### `feedback_events`

Целевой protected quality log:

- type: `thumbs_down`, `unrecognized`, `repeated_clarification`;
- минимальный redacted context;
- reason;
- creation/expiry/deletion timestamps.

Начальный срок хранения — 30 дней, если он не изменён отдельным решением.

### `calendar_sync_jobs`

Будущая очередь одностороннего export:

- booking reference;
- operation;
- status;
- attempts;
- next attempt;
- safe error;
- timestamps.

Calendar error не откатывает business operation в PostgreSQL.

## 6. Удаление и архивирование

Owner foreign keys для рабочих данных используют защитную семантику `RESTRICT`, чтобы случайное удаление user не уничтожало весь business history.

Client and business deletion должны быть отдельными контролируемыми operations с:

- role check;
- owner check;
- confirmation;
- audit;
- retention decision.

На ранних этапах предпочтительно archive/disable вместо physical delete.

## 7. Внутреннее обозначение и публичное имя

Пример только с synthetic data:

```text
public_name: Тестовый клиент A
internal_alias: Тестовый клиент A — дополнительное время
internal_notes: Предпочитает вечерние записи
```

Правила:

- бот отдельно подтверждает public name;
- internal alias не используется в обращении к клиентке;
- internal note не попадает в outbound message;
- personal duration хранится структурированно, а не внутри alias/note;
- fuzzy match не выполняет automatic merge.

## 8. GitHub и тестовые данные

Разрешены только synthetic values, например:

```text
public_name = "Тестовый клиент A"
phone = "+70000000001"
telegram_user_id = 100000001
```

Запрещены реальные:

- имена;
- телефоны;
- Telegram IDs;
- записи;
- фотографии записной книжки;
- `.env`;
- database dumps;
- access logs with personal payload.

## 9. Hermes и память

Встроенные profile memory and user profile отключены:

```text
memory.memory_enabled=false
memory.user_profile_enabled=false
```

Причина — отсутствие надёжной tenant isolation для бизнес-данных нескольких Telegram users.

Hermes может использовать текущую conversation session, но persistent state получает только через restricted Booking API tools.

## 10. Backup and recovery

До real-data pilot обязательны:

- scheduled backup;
- copy outside active database and single VPS disk;
- encryption/access control as applicable;
- backup result log;
- restore into separate database;
- documented restore verification.

Проверенная persistence Docker volume после restart не является backup.

## 11. Исходящие сообщения

Будущий outbound component получает только explicitly whitelisted public fields.

Перед отправкой проверяется отсутствие:

- internal aliases;
- internal notes;
- technical IDs;
- credentials;
- raw audit payload;
- unrelated client data.
