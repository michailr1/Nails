# Бизнес-процессы

Дата актуализации: **13 июля 2026 года**.

## 1. Статус документа

Этот документ описывает целевые процессы MVP. На текущем production-этапе реализован только технический каркас NAILS-002A и безопасный Telegram-профиль.

Пока **не подключены**:

- рабочее сохранение onboarding из Telegram;
- поиск реальных окон;
- создание, перенос и отмена записей;
- aliases and notes;
- feedback events;
- Google Calendar.

Следующий активный срез — NAILS-002B onboarding API.

## 2. Общие правила всех процессов

- Telegram ID и роль не берутся из текста сообщения.
- Booking API получает trusted identity от ограниченного Hermes tool.
- Все операции фильтруются по owner.
- Draft data не участвуют в рабочем расписании до подтверждения.
- Опасное изменение сначала показывается пользователю.
- Повторный запрос не создаёт duplicate благодаря idempotency.
- Модель не сообщает об успехе до подтверждённой transaction response.
- Internal alias никогда не используется как public name.
- Calendar export не входит в business transaction.

## 3. Первичный onboarding

### 3.1 Знакомство

Бот:

- представляется;
- объясняет только реально включённые возможности;
- отдельно сообщает, если рабочее сохранение ещё не подключено;
- объясняет подтверждения и защиту внутренних пометок;
- отвечает на вопросы;
- предлагает начать интервью без давления.

До NAILS-002B допустимо только тестовое интервью в текущей conversation session.

### 3.2 Порядок интервью

1. Рабочий график.
2. Услуги, цены и стандартные длительности.
3. Буферы.
4. Записи наперёд.

Каждый блок проходит цикл:

```text
collect draft
  → validate
  → show summary
  → confirm or correct
  → mark confirmed
```

### 3.3 Pause and resume

После NAILS-002B состояние хранится в `onboarding_states` and `onboarding_drafts`.

После restart Hermes or backend пользователь должен продолжить с последнего подтверждённого шага.

### 3.4 Complete onboarding

Onboarding считается завершённым только когда обязательные блоки подтверждены. Booking API фиксирует completion and audit event.

## 4. Поиск свободного времени

Мастер задаёт услугу и период обычным сообщением.

Booking API:

1. определяет owner and role;
2. находит active service;
3. выбирает standard or client-specific duration;
4. добавляет buffers;
5. применяет schedule rules and exceptions;
6. исключает существующие bookings and blocks;
7. возвращает варианты в configured timezone.

Модель не придумывает duration, price or availability.

## 5. Создание минимального клиента

В первом scheduling happy path:

- `public_name` обязательно;
- contact optional;
- выполняется exact normalized-name search;
- при совпадении пользователь подтверждает существующую карточку;
- при отсутствии совпадения подтверждает создание новой.

Fuzzy search, aliases, notes and duplicate merge относятся к NAILS-004.

## 6. Диалоговое формирование расширенной клиентской базы

После NAILS-004 при новом обозначении клиентки система:

1. нормализует input;
2. ищет exact public-name matches;
3. ищет internal aliases;
4. показывает возможные typo/duplicate candidates;
5. просит выбрать существующую карточку или создать новую;
6. отдельно подтверждает public name;
7. отдельно сохраняет internal alias;
8. запрашивает optional contact;
9. возвращается к исходной операции.

Automatic merge запрещён.

## 7. Публичное имя и внутренние данные

Карточка разделяет:

- `public_name` — допустимо для будущего обращения к клиентке;
- `internal_alias` — только private search by master/admin;
- `internal_notes` — закрытые рабочие заметки;
- `client_service_overrides` — structured duration/price corrections.

Свободный текст notes не является источником business rules.

## 8. Создание записи

Обязательные данные:

- owner;
- client;
- service;
- start time;
- calculated end time;
- price snapshot;
- currency;
- idempotency key.

Поток:

```text
request
  → resolve identity/role/owner
  → validate client and service
  → calculate duration and buffers
  → check overlap
  → show summary
  → confirm
  → transaction: booking + audit
  → success response
```

Изменение catalog price не меняет historical booking snapshot.

## 9. Перенос записи

1. Найти booking только в owner scope.
2. Показать current parameters.
3. Проверить new interval.
4. Показать new summary and conflicts.
5. Получить confirmation.
6. Update booking and write audit.
7. После NAILS-006 создать calendar sync job.

Ошибка Google Calendar не отменяет перенос в PostgreSQL.

## 10. Отмена записи

1. Найти booking in owner scope.
2. Показать booking.
3. Запросить confirmation.
4. Изменить status to `cancelled`.
5. Сохранить audit.
6. Позднее создать calendar delete/update job.

Physical deletion обычной записи не используется вместо status transition.

## 11. Блокировка времени

Мастер может закрыть:

- interval;
- full day;
- date range.

Блоки участвуют в availability calculation. Interval crossing midnight должен быть явно разбит по local dates или корректно обработан timezone-aware logic.

## 12. Просмотр расписания

Целевые запросы:

- day;
- week;
- period;
- client;
- service;
- free windows.

Ответы показывают только данные owner и не раскрывают internal notes без явного запроса доверенного пользователя.

## 13. «Как обычно»

После NAILS-005:

1. найти последнюю подходящую completed booking;
2. взять service from structured history;
3. применить client service override;
4. показать parameters;
5. предложить free windows;
6. создать новую booking after confirmation.

## 14. Персональная длительность

Хранится в `client_service_overrides`, а не в alias or notes.

При расчёте availability override имеет приоритет над standard service duration согласно утверждённому business rule.

## 15. No-show

`no_show` — отдельный status, не `cancelled`.

Количество no-show вычисляется по history. Отдельный mutable counter в client card не используется.

## 16. Задержка процедуры

Мастер сообщает expected or actual delay.

Система:

- сохраняет expected/actual timing;
- показывает conflict with next booking;
- не двигает следующие bookings автоматически;
- предлагает варианты только как draft operations;
- требует отдельное confirmation для каждого переноса.

## 17. Завершение визита и выручка

После завершения можно подтвердить actual price.

Revenue:

- uses `bookings.price_amount` snapshot;
- includes only `completed` bookings;
- excludes cancelled;
- includes no-show only by actually retained amount, when supported;
- does not mix currencies without explicit conversion;
- manual correction is audited.

## 18. Утренняя сводка

После NAILS-005 master may enable daily summary.

Notification settings должны позволять выбрать presentation mode where applicable. Отправка должна использовать только owner data and safe public/internal formatting for the master channel.

## 19. Обратная связь

Целевой feedback process:

- thumbs-down or text equivalent;
- minimal context;
- secret removal;
- contact masking where possible;
- admin-only detailed access;
- configurable retention, initial target 30 days;
- manual deletion.

До создания `feedback_events` нельзя утверждать, что feedback сохранён.

## 20. Фотоимпорт

Vision может прочитать фотографию расписания или записной книжки, но результат всегда является draft:

```text
image
  → recognition
  → structured preview
  → master correction
  → explicit confirmation
  → Booking API write
```

Photo import не блокирует основной happy path. Реальные photos не попадают в GitHub.

## 21. Google Calendar

После NAILS-006:

- PostgreSQL remains source of truth;
- export is one-way;
- write success does not depend on Calendar;
- retries use backoff;
- exhausted retries create admin-visible error;
- reconciliation detects drift.

## 22. Административные процессы

`admin` управляет через строго определённые functions:

- users and roles;
- allowlist outside LLM;
- system settings;
- safe audit;
- diagnostics;
- archive/restore;
- confirmed duplicate merge when implemented;
- test-data cleanup.

Admin не получает arbitrary shell or SQL через Telegram.

## 23. Pilot process

1. Полный synthetic onboarding role `admin`.
2. Synthetic schedule and booking tests.
3. Restart/resume tests.
4. Backup and restore-test.
5. Delete synthetic data.
6. Add master to pilot allowlist and backend role.
7. Parallel old/new schedule.
8. Reconciliation and feedback review.
9. Основной переход только после explicit master trust.
