# Приватность и модель данных

Дата актуализации: **20 сентября 2026 года**.

## 1. Основные правила

- PostgreSQL — источник истины.
- Все business entities owner-scoped там, где это требуется моделью.
- Реальные данные не должны попадать в GitHub/CI/технические примеры.
- Master trusted identity и client transport identity разделены.
- Private client fields не входят в client-facing responses.
- Start-token → owner разрешается только сервером.
- Public profile мастера не строится автоматически из Telegram account fields.

## 2. Миграционное состояние

Alembic head в текущем `main`: **0025**.

Схема развилась далеко дальше первоначального `0001`. Помимо core master tables добавлены:

- web auth/session primitives;
- service catalog/composition и booking snapshots;
- owner-scoped client binding primitives;
- client Telegram contexts;
- contact forwards;
- booking requests;
- client booking drafts;
- notification outbox/linking state;
- user timezone;
- master forward dedupe;
- booking request note.

Точные columns/constraints смотреть в `backend/alembic/versions/*` и models.

## 3. Master business data

К доверенному контуру относятся:

- services/catalog;
- clients;
- bookings;
- availability/schedule;
- onboarding;
- audit/feedback;
- web session/auth state;
- statistics-derived data.

Внутренние поля карточки клиентки могут включать aliases/notes/preferences и не являются публичными.

## 4. Client Telegram identity

Client Telegram identity отделена от operator table `users`.

Binding owner-scoped: одна и та же Telegram-клиентка может иметь независимые отношения с несколькими masters.

Нельзя использовать Telegram ID как публичный display field.

## 5. Master link token

Deep-link token является capability для server-side resolution мастера.

Требования:

- owner не принимается от client UI;
- невалидный/просроченный/revoked token не создаёт arbitrary binding;
- token не должен раскрывать numeric owner identity пользователю.

## 6. Public master profile

Публично допустимы только явно предназначенные поля:

- `display_name`;
- `public_contact` при explicit opt-in;
- публичная витрина/прайс.

Не публикуются автоматически:

- numeric Telegram ID;
- personal Telegram first/last name;
- Telegram username;
- внутренние identifiers.

## 7. BookingRequest vs Booking

`BookingRequest(pending)` не является подтверждённой записью и не должен блокировать slot.

`Booking` появляется только после master approve и повторной доменной проверки.

## 8. Client draft

Draft хранит временный выбор услуги/addons/slot и имеет TTL.

Draft не даёт дополнительных прав и не считается Booking/Request до submit.

## 9. Outbox

Notification outbox хранит минимально необходимое для транзакционной доставки. Runtime выполняет claim/send/ack и не получает direct DB credentials.

Delivery/reachability status не должен раскрывать private business data.

## 10. Contact flow

Телефон принимается только через проверенный Telegram contact ownership flow.

Имя/телефон могут использоваться для preselect/candidate assistance мастеру, но **не** для автоматического присоединения существующей карточки.

## 11. Audit

Audit не должен превращаться в копию персональных данных. Для client операций не следует писать в безопасный audit raw Telegram ID, телефон, свободный текст и private notes, если это не требуется отдельным нормативным решением.

## 12. GitHub/CI

В репозитории допустимы:

- schema;
- migrations;
- code;
- synthetic tests;
- placeholders.

Недопустимы:

- production secrets;
- реальные Telegram bot tokens/internal keys;
- реальные карточки/телефоны;
- выгрузки production DB.
