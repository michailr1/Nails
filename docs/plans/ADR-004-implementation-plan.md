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
- выполняет commit;
- возвращает проверяемое представление результата.

Approve заявки должен вызывать этот путь, а не копировать его. Существующий commit boundary сохраняется; согласованность заявки и записи достигается повторяемым idempotent recovery-flow, описанным ниже, а не большим рефакторингом стабильного booking path.

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

### 3.2 Нельзя автоматически присоединять чужую карточку

Имя, username и номер телефона из сообщения клиентки не являются достаточным доказательством, что существующая карточка `Client` принадлежит ей.

Поэтому:

- совпадение имени никогда не привязывает identity автоматически;
- совпадение телефона может быть только подсказкой мастеру, даже если Telegram contact проверен через `contact.user_id == from.id`;
- новая Telegram identity сначала хранит заявленное публичное имя и необязательный подтверждённый Telegram contact;
- привязку к существующей карточке явно подтверждает мастер;
- если мастер подтверждает, что это новая клиентка, создаётся новая минимальная карточка и identity связывается с ней;
- клиентка не получает private данные выбранной мастером карточки.

Первую привязку можно выполнить одновременно с решением первой заявки, чтобы не строить отдельный длинный onboarding.

### 3.3 Разделение ключей

Client bot не получает master internal API key и не может вызывать master/admin endpoints. Master/Hermes/web не используют client key как замену существующей identity.

Внешний Telegram Bot API token и оба внутренних ключа остаются только в production env. В GitHub не добавляются реальные токены, Telegram ID или owner UUID.

### 3.4 Минимальная публичная поверхность

Client API остаётся внутренним для отдельного bot runtime. Booking API не публикуется в интернет. Rate limit и Telegram abuse protection применяются на bot/runtime boundary и дополнительно на backend client mutations.

Свободный текст не интерпретируется моделью и не влияет на доменные аргументы. Его пересылка мастеру — отдельный ограниченный flow без сохранения текста в audit.

## 4. Минимальная модель данных

Миграция expand-only и обратно совместима минимум с предыдущим application release.

### 4.1 `client_telegram_identities`

Назначение — представить Telegram-клиентку внутри одного owner scope, не используя операторскую таблицу `users` и не захватывая существующую карточку по совпадению имени.

Минимальные поля:

- `id` UUID;
- `owner_user_id` FK → `users.id`;
- `client_id` nullable FK → `clients.id`;
- `telegram_user_id` bigint;
- `status`: `pending|active|revoked`;
- `requested_public_name`;
- `requested_phone` nullable — только из проверенного Telegram contact;
- timestamps.

Инварианты:

- unique `(owner_user_id, telegram_user_id)`;
- partial unique `(owner_user_id, client_id)` для non-null `client_id` в первой версии;
- `active` требует `client_id`;
- owner карточки обязан совпадать с `owner_user_id` identity;
- существующая карточка не связывается без master decision;
- после успешной привязки временные requested-поля можно очистить;
- `revoked` сохраняет историю заявок и записей.

### 4.2 `booking_requests`

Назначение — хранить намерение клиентки до решения мастера. Это не `Booking` и не резерв времени.

Минимальные поля:

- `id` UUID;
- `owner_user_id`;
- `client_identity_id`;
- `client_id` nullable до master resolution первой identity;
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
- `approved` допустим только с `client_id` и `booking_id`;
- client cancel допустим только для своей `pending` заявки;
- master decision выполняется owner-scoped;
- audit хранит только безопасные метаданные: статус, число дополнений, локальную дату/время и факт создания booking — без телефона, notes, Telegram ID и свободного текста.

### 4.3 Почему не новый статус `Booking`

`Booking` означает подтверждённый визит и резервирует интервал. Добавление `pending` в `BookingStatus` заставило бы все календарные, overlap, digest, финализацию, экспорт и отчёты различать заявку и запись. Отдельная небольшая таблица устраняет этот класс смешения и сохраняет существующие инварианты Booking.

## 5. Семантика identity и заявки

### 5.1 Первый контакт

1. Bot runtime получает Telegram Update и проверяет, что callback/contact принадлежит `from.id`.
2. Backend разрешает server-side owner и Telegram user ID через `ClientRequestIdentity`.
3. Identity создаётся или читается по `(owner_user_id, telegram_user_id)`.
4. Клиентка указывает публичное имя; телефон принимается только как Telegram contact с совпадающим `user_id`.
5. Существующая карточка по имени или телефону автоматически не присоединяется.
6. Клиентка может посмотреть публичный прайс и отправить первую заявку; мастер разрешает identity при её рассмотрении.

### 5.2 Создание заявки клиенткой

1. Клиентка выбирает только активные публичные позиции текущего owner.
2. Backend повторно проверяет base/addon состав и желаемое время.
3. Создаётся `pending` заявка и публичный snapshot.
4. Free slots не меняются.
5. Повтор с тем же idempotency key возвращает ту же заявку; другой payload с тем же key даёт conflict.
6. Неактивная identity или identity другого owner не может создать заявку.

### 5.3 Разрешение карточки мастером

Для первой заявки master decision содержит одно из двух явных решений:

- связать identity с выбранной существующей owner-scoped карточкой;
- создать новую минимальную карточку из подтверждённого мастером публичного имени и затем связать identity.

Backend повторно проверяет, что карточка принадлежит owner и не связана с другой активной Telegram identity. Клиентские аргументы не могут выбрать `client_id`.

### 5.4 Подтверждение мастером

1. Master читает свежую pending-заявку.
2. При необходимости явно разрешает identity по предыдущему разделу.
3. Backend owner-scoped разрешает текущие активные service rows по сохранённым IDs.
4. Формируется существующий `CatalogBookingCreateRequest` с текущими публичными именами и idempotency key, детерминированно производным от ID заявки.
5. Вызывается существующий `create_booking()`.
6. Он заново проверяет выходной, overlap, текущие цену и длительность, сохраняет обычные Booking snapshots и выполняет commit.
7. После проверенного результата отдельным commit заявка становится `approved` и получает `booking_id`.

Существующий `create_booking()` уже коммитит Booking, поэтому approve является recoverable two-step, а не одной транзакцией:

- если процесс завершился после commit Booking, но до обновления заявки, повтор approve использует тот же booking idempotency key;
- `create_booking()` возвращает уже созданную запись без дубля;
- backend затем завершает перевод заявки в `approved`;
- запрос никогда не помечается approved до подтверждённого Booking result.

Это сохраняет стабильный booking path и закрывает crash-gap идемпотентным восстановлением.

Если каталог или слот изменился, заявка остаётся `pending`, а мастер получает конкретную причину. Автоматический подбор другого времени и скрытая замена процедуры запрещены.

### 5.5 Отклонение и отмена

- мастер может отклонить только owner-scoped `pending` заявку;
- клиентка может отменить только собственную `pending` заявку;
- reason в первой версии — фиксированный код/шаблон, не обязательное свободное поле;
- approved/rejected/cancelled являются terminal для этой заявки;
- отмена или отказ не меняют расписание и не создают Booking.

## 6. Audit

`AuditEvent.actor_user_id` ссылается только на операторскую таблицу `users`.

Поэтому:

- master decisions используют фактический `actor_user_id` мастера;
- client mutations используют `actor_user_id=NULL` и безопасный `actor_type=client_bot` в `safe_changes`;
- Telegram user ID, телефон, имя и содержимое callback/free text в audit не записываются;
- object ID может ссылаться на identity/request, но наружу клиентке не раскрывает внутреннюю структуру.

## 7. API-срезы

Названия путей уточняются в implementation PR, но границы фиксированы.

### Client transport

- публичное представление активного каталога;
- предлагаемые свободные окна;
- создать/обновить собственную pending identity с заявленным именем и проверенным contact;
- создать заявку;
- список собственных заявок;
- отменить собственную pending-заявку;
- список собственных подтверждённых будущих записей — поздний Slice D.

### Master transport

Существующая master identity:

- список pending-заявок текущего owner;
- карточка одной заявки;
- resolve identity: link existing или create new;
- approve;
- reject.

Web BFF и Hermes при необходимости являются интерфейсами к этим операциям, а не отдельными источниками бизнес-логики.

## 8. Разбивка реализации

### Slice A — backend foundation

- expand-only migration;
- модели и schemas;
- отдельная client transport identity;
- public catalog/free-slot presenters;
- client identity/create/list/cancel request;
- master list/resolve/approve/reject;
- recoverable approve после внутреннего booking commit;
- audit, idempotency, owner isolation и privacy tests;
- backup/restore contract для новых таблиц.

### Slice B — кабинет мастера

- раздел входящих заявок;
- разрешение первой identity без автоматического присоединения карточки;
- полная понятная сводка;
- подтверждение/отказ;
- fresh readback и конфликт без утечки private fields.

### Slice C — deterministic Telegram bot

- отдельный token и runtime;
- fixed templates и inline keyboard;
- сценарий `прайс → процедура → дополнения → окно → сводка → заявка`;
- проверка callback/contact ownership;
- rate limits;
- никакого LLM, Hermes, arbitrary HTTP или свободной генерации обещаний.

### Slice D — свои заявки и записи

- клиентка видит только собственные заявки и будущие записи;
- запросы на отмену/перенос мастеру;
- прямое изменение подтверждённой записи не вводится без отдельного продуктового решения;
- напоминания — отдельный последующий slice.

## 9. Обязательные regression-сценарии Slice A

1. Client key не даёт доступ к master/admin endpoints.
2. Master internal key не подменяет client Telegram identity.
3. Owner/client/role/Telegram ID нельзя передать в body и выбрать произвольно.
4. Имя или телефон не присоединяют identity к существующей карточке автоматически.
5. Telegram contact принимается только при `contact.user_id == from.id`.
6. Другой Telegram user не читает и не отменяет заявку.
7. Другой owner не читает, не связывает и не подтверждает заявку.
8. Public responses не содержат private client fields и внутренних service IDs.
9. Pending-заявка не блокирует слот.
10. Две pending-заявки могут просить один слот; первая успешная approval создаёт Booking, вторая получает overlap при approval.
11. Повтор client create и master approve с тем же idempotency key не создаёт дубликат.
12. Idempotency key с другим payload даёт conflict.
13. Crash/retry между Booking commit и request approval восстанавливает approved state без второго Booking.
14. Архивированная/чужая base или addon позиция не используется.
15. Approve создаёт обычные immutable Booking snapshots.
16. Ошибка `create_booking()` не переводит заявку в approved.
17. Client cancel и master reject не затрагивают Booking и расписание.
18. Одна owner-scoped карточка не связывается с двумя активными Telegram identities.
19. Audit client mutation использует nullable actor и не содержит Telegram ID, телефон, имя, private notes, token или свободный текст.
20. Clean migration, repeated migration, previous-release compatibility и isolated restore проходят.

## 10. Сознательно вне первой версии

- публичный Hermes или другой LLM;
- FAQ-генерация;
- автоподтверждение;
- hold/TTL/очередь слотов;
- waitlist;
- tenant selection;
- multi-master SaaS и биллинг;
- автоматическая привязка существующей клиентской карточки по имени/телефону;
- совместимость дополнений как новая матрица;
- количество для per-unit;
- скидки и промокоды;
- произвольные клиентские комментарии в доменной заявке;
- отдельный frontend framework или новая публичная web-поверхность.

## 11. Release boundary

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
