# Onboarding API

Статус: реализовано в NAILS-002B, production deployment выполняется отдельно после merge.

## Назначение

API хранит возобновляемое onboarding-интервью независимо от памяти Hermes. Он не создаёт рабочие услуги, график или записи напрямую: на этом этапе сохраняются и подтверждаются только onboarding-блоки.

## Доверенный контекст

Все endpoints, кроме `/health` и `/ready`, требуют headers:

```text
X-Nails-Internal-Key
X-Telegram-User-ID
X-Request-ID
```

- `X-Nails-Internal-Key` — общий секрет только между backend и будущим ограниченным Hermes domain tool;
- `X-Telegram-User-ID` — фактический ID из trusted gateway context;
- `X-Request-ID` — идентификатор запроса для audit; если отсутствует, backend создаёт UUID.

Модель не должна иметь возможность произвольно выбирать Telegram ID. До NAILS-002C API не подключается к Hermes.

Backend разрешает операции только активным пользователям PostgreSQL с ролью `master` или `admin`.

## Endpoints

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

Подтверждение выполняется в указанном порядке.

## Draft и confirmed data

Для каждого section хранятся:

- `payload` — текущий редактируемый draft;
- `confirmed_payload` — последняя подтверждённая версия;
- `revision` — номер текущего draft;
- `confirmed_revision` — номер последней подтверждённой версии;
- `is_confirmed` — подтверждён ли текущий revision;
- `confirmed_at`.

После изменения подтверждённого блока:

- draft revision увеличивается;
- текущая revision становится неподтверждённой;
- последняя подтверждённая версия остаётся отдельно доступной;
- рабочая логика в будущем должна использовать только `effective_payload`;
- после повторного подтверждения новая revision становится effective.

Изменение и повторное подтверждение upstream section инвалидирует подтверждения downstream sections, которые могли зависеть от старых данных.

## Валидация

### Schedule

- weekday: `0..6`;
- рабочий день требует start/end;
- end позже start;
- weekday values уникальны;
- для подтверждения требуется описание всех семи дней.

### Services

- непустое public name;
- names уникальны без учёта регистра;
- price неотрицательная;
- ISO currency из трёх заглавных букв;
- duration `5..1440` минут.

### Buffers

- service name должен ссылаться на подтверждённую service;
- before/after `0..240` минут;
- одна строка на service.

### Future bookings

- public client name;
- optional phone;
- service name из подтверждённого services block;
- timezone-aware start datetime.

## Состояния

```text
not_started
in_progress
paused
completed
```

`start` идемпотентен для уже активного интервью. Для paused state используется `resume`. Completed onboarding повторно не запускается этим endpoint.

`pause`, `resume`, повторное confirmation одной revision и повторное `complete` не создают дубликаты действий.

## Audit

Фиксируются безопасные события:

```text
onboarding.started
onboarding.draft_saved
onboarding.section_confirmed
onboarding.paused
onboarding.resumed
onboarding.completed
```

Audit не содержит полный onboarding payload, телефон или другие рабочие данные. Сохраняются только section, revision, status и список invalidated sections.

Validation errors также не возвращают исходный payload: только безопасные `type`, `location` и `message`.

## Migration

NAILS-002B добавляет Alembic revision:

```text
0002_onboarding_confirmed_revisions
```

Migration добавляет отдельный confirmed payload и revision metadata к `onboarding_drafts` и сохраняет совместимость с ранее подтверждёнными строками.

## Что не входит в NAILS-002B

- автоматическое создание пользователей;
- подключение Hermes tools;
- материализация confirmed blocks в рабочие `services`, `schedule_rules`, `clients`, `bookings`;
- поиск свободных окон;
- scheduling operations;
- Google Calendar.

Следующий шаг — NAILS-002C: безопасный Hermes domain tool, который сам берёт Telegram ID из gateway context и вызывает только эти endpoints.
