# ADR-004 — план реализации клиентского контура

Дата: **21 июля 2026 года**  
Статус: **implementation plan принят к review**  
Активная задача: **Issue #171**

Нормативные источники:

- [`ADR-004-client-contour-without-llm.md`](../decisions/ADR-004-client-contour-without-llm.md);
- [`product-principles.md`](../product/product-principles.md);
- [`engineering-principles.md`](../operations/engineering-principles.md);
- [`roles-and-permissions.md`](../roles-and-permissions.md).

## 1. Цель

Первый клиентский контур — отдельный детерминированный Telegram-бот без LLM. Клиентка кнопками:

1. смотрит публичную часть прайса;
2. выбирает основную процедуру и дополнения;
3. смотрит предлагаемые свободные окна;
4. отправляет заявку;
5. видит статус только своих заявок и подтверждённых записей.

Заявка не становится записью автоматически. Мастер получает сводку и явно подтверждает или отклоняет её. Подтверждение создаёт обычный `Booking` через существующую доменную операцию и повторно проверяет фактическое состояние расписания.

## 2. Проверенная инвентаризация существующего

Новый контур обязан переиспользовать существующее ядро.

### 2.1 Каталог

`Service` уже содержит:

- owner scope;
- `base|addon`;
- `fixed|range|per_unit|on_request`;
- публичное имя и описание;
- раздел прайса и порядок;
- обычную длительность основной процедуры;
- дополнительное время дополнения;
- buffers и признак активности.

Параллельная таблица публичного прайса не создаётся.

### 2.2 Расписание

Существующие `AvailabilityInterval`, `find_free_slots`, ADR-006 и overlap-проверка уже определяют:

- целый выходной как реальный запрет;
- фактическое пересечение с учётом reserved interval;
- положительные интервалы как подсказки, а не жёсткую границу;
- повторную server-side проверку при записи.

Отдельный клиентский календарный движок не создаётся.

### 2.3 Запись

`create_booking()` уже:

- блокирует расписание владельца;
- проверяет idempotency;
- owner-scoped разрешает клиентку, основную процедуру и дополнения;
- считает длительность и ценовую семантику;
- проверяет выходной и overlap;
- сохраняет immutable snapshots состава, цены, времени и buffers;
- пишет audit;
- возвращает проверяемое представление результата.

Approve заявки должен вызывать этот путь, а не копировать его.

### 2.4 Карточка клиентки

`Client` уже содержит публичное имя и контакт, а также внутренние поля мастера. Клиентский ответ может содержать только минимальную публичную часть. Запрещено отдавать:

- `private_alias`;
- общие notes;
- заметки о ногтях и коже;
- чувствительность и ограничения;
- предпочтения по стилю и общению;
- внутренние ID, кроме непрозрачных идентификаторов собственных заявок, необходимых клиентскому UI.

### 2.5 Доверенная операторская identity

Текущий `RequestIdentity` и таблица `users` предназначены для доверенных `master|admin`:

- `users.telegram_user_id` глобально уникален;
- internal auth разрешает только активного мастера или администратора;
- owner scope равен `RequestIdentity.user_id`.

Публичных клиенток нельзя добавлять в этот же auth-flow: это смешало бы доверенную операторскую identity с недоверенной публичной аудиторией.

## 3. Security boundary

### 3.1 Отдельная транспортная identity

Вводится `ClientRequestIdentity`, не расширяющая полномочия `RequestIdentity`.

Она формируется только backend dependency из:

- отдельного client-bot internal key;
- Telegram user ID, полученного bot runtime из проверенного Telegram Update;
- единственного owner, заданного server-side конфигурацией первого запуска.

Client endpoint не принимает из body/query:

- `owner_user_id`;
- `client_id`;
- роль;
- чужой Telegram ID;
- статус решения мастера.

Первый запуск рассчитан на одного мастера. Выбор мастера клиенткой, tenant routing и multi-master registry не вводятся.

### 3.2 Разделение ключей

Client bot не получает master internal API key и не может вызывать master/admin endpoints. Master/Hermes/web не используют client key как замену существующей identity.

Внешний Telegram Bot API token и оба внутренних ключа остаются только в production env. В GitHub не добавляются реальные токены, Telegram ID или owner UUID.

### 3.3 Минимальная публичная поверхность

Client API остаётся внутренним для отдельного bot runtime. Booking API не публикуется в интернет. Rate limit и Telegram abuse protection применяются на bot/runtime boundary и дополнительно на backend client mutations.

Свободный текст не интерпретируется моделью и не влияет на доменные аргументы. Его пересылка мастеру — отдельный ограниченный flow без сохранения текста в audit.

## 4. Минимальная модель данных

Миграция expand-only и обратно совместима минимум с предыдущим application release.

### 4.1 `client_telegram_identities`

Назначение — связать Telegram-клиентку с owner-scoped карточкой `Client`, не используя операторскую таблицу `users`.

Минимальные поля:

- `id` UUID;
- `owner_user_id` FK → `users.id`;
- `client_id` FK → `clients.id`;
- `telegram_user_id` bigint;
- `is_active` boolean;
- timestamps.

Инварианты:

- unique `(owner_user_id, telegram_user_id)`;
- unique `(owner_user_id, client_id)` для первой версии;
- owner карточки обязан совпадать с `owner_user_id` identity;
- деактивация сохраняет историю заявок и записей.

### 4.2 `booking_requests`

Назначение — хранить намерение клиентки до решения мастера. Это не `Booking` и не резерв времени.

Минимальные поля:

- `id` UUID;
- `owner_user_id`;
- `client_identity_id`;
- `client_id`;
- `base_service_id`;
- `addon_service_ids` JSONB со списком выбранных owner-scoped UUID;
- `catalog_items_snapshot` JSONB — публичный снимок того, что увидела клиентка;
- `requested_starts_at` timestamptz;
- ориентиры `duration_minutes`, `price_type`, `price_min`, `price_max`, `price_unit`, `currency`;
- `status`: `pending|approved|rejected|cancelled`;
- `idempotency_key`;
- `decision_actor_user_id`, `decided_at`;
- `booking_id` после успешного approve;
- timestamps.

Инварианты:

- unique `(owner_user_id, idempotency_key)`;
- pending-заявка не участвует в overlap и не изменяет free slots;
- terminal status не возвращается в `pending`;
- `approved` допустим только с `booking_id`;
- client cancel допустим только для своей `pending` заявки;
- master decision выполняется под owner schedule lock;
- audit хранит только безопасные метаданные: статус, число дополнений, локальную дату/время и факт создания booking — без телефона, notes и свободного текста.

### 4.3 Почему не новый статус `Booking`

`Booking` означает подтверждённый визит и резервирует интервал. Добавление `pending` в `BookingStatus` заставило бы все календарные, overlap, digest, финализацию, экспорт и отчёты различать заявку и запись. Отдельная небольшая таблица устраняет этот класс смешения и сохраняет существующие инварианты Booking.

## 5. Семантика заявки

### 5.1 Создание клиенткой

1. Bot runtime получает Telegram Update.
2. Backend разрешает `ClientRequestIdentity`.
3. Клиентка выбирает только активные публичные позиции текущего owner.
4. Backend повторно проверяет base/addon состав и желаемое время.
5. Создаётся `pending` заявка и публичный snapshot.
6. Free slots не меняются.
7. Повтор с тем же idempotency key возвращает ту же заявку; другой payload с тем же key даёт conflict.

### 5.2 Подтверждение мастером

1. Master читает свежую pending-заявку.
2. Backend owner-scoped разрешает текущие активные service rows по сохранённым IDs.
3. Формируется существующий `CatalogBookingCreateRequest` с текущими публичными именами и отдельным idempotency key, производным от заявки.
4. Вызывается существующий `create_booking()`.
5. Он заново проверяет выходной, overlap, текущие цену и длительность и сохраняет обычные Booking snapshots.
6. Только после успешного создания/readback заявка становится `approved` и получает `booking_id`.

Если каталог или слот изменился, заявка остаётся `pending`, а мастер получает конкретную причину. Автоматический подбор другого времени и скрытая замена процедуры запрещены.

### 5.3 Отклонение и отмена

- мастер может отклонить только owner-scoped `pending` заявку;
- клиентка может отменить только собственную `pending` заявку;
- reason в первой версии — фиксированный код/шаблон, не обязательное свободное поле;
- approved/rejected/cancelled являются terminal для этой заявки.

## 6. API-срезы

Названия путей уточняются в implementation PR, но границы фиксированы.

### Client transport

- публичное представление активного каталога;
- предлагаемые свободные окна;
- создать или привязать минимальную карточку клиентки;
- создать заявку;
- список собственных заявок;
- отменить собственную pending-заявку;
- список собственных подтверждённых будущих записей — поздний Slice D.

### Master transport

Существующая master identity:

- список pending-заявок текущего owner;
- карточка одной заявки;
- approve;
- reject.

Web BFF и Hermes при необходимости являются интерфейсами к этим операциям, а не отдельными источниками бизнес-логики.

## 7. Разбивка реализации

### Slice A — backend foundation

- expand-only migration;
- модели и schemas;
- отдельная client transport identity;
- public catalog/free-slot presenters;
- client create/list/cancel request;
- master list/approve/reject;
- audit, idempotency, owner isolation и privacy tests;
- backup/restore contract для новых таблиц.

### Slice B — кабинет мастера

- раздел входящих заявок;
- полная понятная сводка;
- подтверждение/отказ;
- fresh readback и конфликт без утечки private fields.

### Slice C — deterministic Telegram bot

- отдельный token и runtime;
- fixed templates и inline keyboard;
- сценарий `прайс → процедура → дополнения → окно → сводка → заявка`;
- rate limits;
- никакого LLM, Hermes, arbitrary HTTP или свободной генерации обещаний.

### Slice D — свои заявки и записи

- клиентка видит только собственные заявки и будущие записи;
- запросы на отмену/перенос мастеру;
- прямое изменение подтверждённой записи не вводится без отдельного продуктового решения;
- напоминания — отдельный последующий slice.

## 8. Обязательные regression-сценарии Slice A

1. Client key не даёт доступ к master/admin endpoints.
2. Master internal key не подменяет client Telegram identity.
3. Owner/client/role/Telegram ID нельзя передать в body и выбрать произвольно.
4. Другой Telegram user не читает и не отменяет заявку.
5. Другой owner не читает и не подтверждает заявку.
6. Public responses не содержат private client fields и внутренних service IDs.
7. Pending-заявка не исчезает из-за второй pending-заявки и не блокирует слот.
8. Две pending-заявки могут просить один слот; первая успешная approval создаёт Booking, вторая получает overlap при approval.
9. Повтор client create и master approve с тем же idempotency key не создаёт дубликат.
10. Idempotency key с другим payload даёт conflict.
11. Архивированная/чужая base или addon позиция не используется.
12. Approve создаёт обычные immutable Booking snapshots.
13. Ошибка `create_booking()` не переводит заявку в approved.
14. Client cancel и master reject не затрагивают Booking и расписание.
15. Audit не содержит телефон, private notes, Telegram token и свободный текст.
16. Clean migration, repeated migration, previous-release compatibility и isolated restore проходят.

## 9. Сознательно вне первой версии

- публичный Hermes или другой LLM;
- FAQ-генерация;
- автоподтверждение;
- hold/TTL/очередь слотов;
- waitlist;
- tenant selection;
- multi-master SaaS и биллинг;
- совместимость дополнений как новая матрица;
- количество для per-unit;
- скидки и промокоды;
- произвольные клиентские комментарии в доменной заявке;
- отдельный frontend framework или новая публичная web-поверхность.

## 10. Release boundary

Каждый runtime slice проходит обычный цикл:

```text
branch
→ PR
→ review + green CI
→ exact open PR-head candidate from origin/pr/<N>
→ GitHub merge того же validated head
→ NAILS_RELEASE_REF=origin/main bash ops/deploy/deploy.sh <exact-main-SHA>
→ production verification
```

Этот planning slice меняет только документацию и не требует production deploy.
