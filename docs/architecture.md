# Архитектура

Дата актуализации: **20 сентября 2026 года**.

## 1. Назначение

Nails состоит из двух пользовательских контуров:

1. доверенный контур мастера — Telegram/Hermes + web-кабинет;
2. недоверенный клиентский Telegram-контур — отдельный deterministic bot без LLM.

Оба используют один доменный FastAPI/PostgreSQL слой. PostgreSQL — источник истины; модель/бот не считаются источником факта об успешной бизнес-операции.

## 2. Фактическая схема

```text
MASTER
Telegram -> Hermes Gateway -> restricted Nails plugins
                         \
                          -> FastAPI -> PostgreSQL
Master Web -> same-origin BFF /

CLIENT
Telegram -> nails-client-bot -> /api/v1/client/* -> FastAPI -> PostgreSQL
                         \
                          -> notification outbox -> Telegram
```

Production API публикуется только на loopback, web идёт через edge/reverse proxy.

## 3. Контур мастера

Hermes profile `nails`:

- получает trusted Telegram identity из gateway context;
- не доверяет Telegram ID/role из текста модели;
- использует restricted onboarding/scheduling plugins;
- не имеет direct SQL/SSH/shell business path;
- постоянные бизнес-данные хранит в PostgreSQL, а не в Hermes memory.

Web-кабинет использует Telegram challenge/session auth и owner-scoped BFF.

## 4. Client contour

Клиентский bot:

- отдельный token и `CLIENT_INTERNAL_API_KEY`;
- отдельный runtime `python -m app.client_bot_v1`;
- не работает внутри Hermes;
- не обращается к PostgreSQL напрямую;
- вся бизнес-логика проходит через client API;
- deterministic UI: callbacks, contact flow, шаблоны, без LLM-команд.

Runtime также дренирует notification outbox и ведёт runtime state/observability.

## 5. ADR-009: one platform bot + multi-master

Нормативный binding:

```text
Telegram deep-link
  -> start_token
  -> server-side token resolution
  -> owner_user_id
  -> owner-scoped client binding
```

Клиент **не может** передать произвольный `owner_user_id` через body/query.

Одна Telegram-клиентка может иметь несколько owner-scoped binding'ов. «Ваши мастера» строится только из её binding'ов; глобального каталога мастеров нет.

Не использовать:

- bot-per-master;
- `CLIENT_OWNER_TELEGRAM_USER_ID`;
- client-selected owner;
- auto-link существующей карточки по имени/телефону.

## 6. Public master profile

`master_public_profile` является публичной проекцией мастера для клиентского контура:

- `display_name` обязателен для активации invite link;
- `public_contact` nullable и публикуется только по explicit opt-in;
- master numeric Telegram ID не раскрывается;
- Telegram personal name/username не публикуются автоматически.

## 7. Заявка клиентки и Booking

`BookingRequest` и `Booking` — разные сущности.

```text
client draft
 -> select composition
 -> free slots
 -> submit BookingRequest(pending)
 -> slot remains free
 -> master resolve/link client
 -> approve
 -> recheck day-off/overlap
 -> create Booking(scheduled)
 -> notify client
```

Pending request не резервирует время. Конфликт при approve не вызывает автоматический перенос.

## 8. Client drafts

Server-side draft хранит выбранную композицию и выбранный slot ограниченное время.

При изменении состава слот пересчитывается/сбрасывается. Цена, длительность и доступность считаются сервером, а не Telegram bot.

## 9. Notifications and reachability

Транзакционные уведомления идут через outbox:

- runtime claim;
- Telegram send;
- ack/retry;
- throttling;
- dedupe/idempotency contracts.

Reachability мастера показывает возможность связаться с клиенткой в Telegram.

## 10. Master web

Основные разделы:

- Calendar;
- Clients;
- My price;
- Statistics.

В account menu находятся:

- public profile;
- settings;
- logout.

Кабинет также показывает входящие client requests, связывание identity, approve/reject и invite links.

## 11. Расписание

ADR-006:

- целый сохранённый day-off — жёсткий запрет;
- фактический overlap active booking — жёсткий запрет;
- positive availability intervals формируют предлагаемые окна, но не являются универсальным запретом для явно заданного мастером времени.

Client free slots используют эффективное расписание и полную длительность композиции.

## 12. Deployment

`compose.yaml` содержит:

- `nails-db`;
- `nails-api`;
- `nails-client-bot`;
- `nails-web`.

Client API/runtime feature flags разрешены только согласованной парой `false/false` или `true/true`. Production deploy проверяет отдельность master/client bot tokens и singleton client runtime.

Единственный постоянный production entrypoint:

```bash
ops/deploy/deploy.sh <exact-main-sha>
```

Pre-merge candidate должен быть изолирован и не менять production checkout/DB/runtime.

## 13. Data model

Alembic head текущего `main`: `0025`.

Помимо core master tables существуют client primitives:

- client Telegram identities/contexts;
- master link tokens/public profile;
- contact forwards;
- booking requests;
- booking drafts;
- notification outbox/linking state;
- request note.

Точный список колонок и constraints всегда проверять по migrations/models.

## 14. Security invariants

- owner scoping обязателен;
- trusted master identity и client transport identity разделены;
- private client fields не выходят в client responses;
- secrets не попадают в GitHub/logs;
- pending request не даёт полномочий Booking;
- public profile не раскрывает raw master identity;
- release только через CI + acceptance contract;
- production data не используется в CI.

## 15. Будущие SaaS-слои

Не реализованы как часть ADR-009:

- billing/subscriptions;
- публичная self-service регистрация мастера;
- SaaS admin dashboard;
- public master directory;
- per-master white-label bots.

Это отдельный roadmap после стабилизации текущего продукта.
