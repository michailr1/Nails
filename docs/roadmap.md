# Roadmap

Дата актуализации: **20 сентября 2026 года**.

Roadmap показывает продуктовый порядок. Exact production/main SHA смотреть через свежий preflight; фактические реализованные возможности — в [`status.md`](status.md).

## Статусы

- ✅ завершено и принято/реализовано;
- 🟡 выполняется или ждёт production acceptance;
- ⬜ запланировано.

## Текущая точка

```text
NAILS-001        ✅ продуктовые и security-инварианты
NAILS-002        ✅ master scheduling + backup/restore
NAILS-003        ✅ рабочее время / ADR-006
Master Web UI    ✅ основной кабинет мастера
ADR-007          ✅ прайс base + addons
ADR-004          ✅ client identity, requests, deterministic bot
ADR-009          ✅ SaaS binding: one platform bot + deep-links + multi-binding
ADR-010          ✅ client notifications/reachability runtime primitives
Client runtime   ✅ встроен в штатный deploy lifecycle
Mobile UX        🟡 точечная production acceptance и регрессии
SaaS onboarding  ⬜ self-service подключение, тарифы и billing
```

## Завершённый рабочий контур мастера ✅

Подтверждены в коде:

- onboarding и persistent settings;
- расписание и исключения по датам;
- прайс, base/addon composition;
- карточки клиенток;
- создание/перенос/отмена/finalization;
- календарь, статистика и выгрузки;
- web auth через Telegram;
- профиль мастера и настройки;
- owner scoping, idempotency, audit, backup/restore.

## Клиентский контур ✅

Старый раздел «ADR-004 🟡» закрыт по фактическому состоянию кода.

Реализованы:

1. **Client foundation**
   - owner-scoped client Telegram identity;
   - booking requests;
   - server-side drafts;
   - public price/free slots;
   - client isolation/security contracts.

2. **Master request flow**
   - входящие заявки в кабинете;
   - resolve/link/create client card;
   - approve/reject;
   - повторная проверка slot conflict;
   - pending request не резервирует Booking.

3. **Deterministic Telegram bot**
   - отдельный runtime и credentials;
   - один platform bot для нескольких мастеров;
   - deep-link/start-token;
   - base service → addons/quantities → date/slot → summary → submit;
   - «Мои записи» и актуальные заявки;
   - короткое пояснение мастеру без превращения текста в доменные аргументы.

4. **SaaS binding / ADR-009**
   - start-token → owner только server-side;
   - public profile мастера;
   - public contact opt-in;
   - multi-binding;
   - «Ваши мастера» только по своим binding'ам;
   - без публичного каталога.

5. **Notifications / reachability**
   - outbox;
   - drainer в client runtime;
   - approve/reject notification;
   - reachability;
   - general/personal invite links;
   - singleton client runtime release invariant.

## Текущая доводка 🟡

Приоритет — не достраивать заново client MVP, а стабилизировать уже работающий продукт:

- mobile layout и Safari visual viewport;
- нижняя 4-tab navigation;
- request cards и confirm dialog;
- invite/profile UX;
- рабочий график и его прозрачность в кабинете (#282/#284; реализованы общий интервал и исключения по датам, но не весь исходный acceptance);
- уменьшение script-order/global override debt;
- механическая защита `main`.

## Следующий крупный продуктовый этап ⬜

### Self-service SaaS onboarding мастеров

Issue #223 остаётся будущим направлением:

- onboarding bot/flow для нового мастера;
- тарифная модель;
- provider оплаты;
- idempotent onboarding order;
- автоматическая активация существующего master lifecycle;
- отмена/истечение/отзыв доступа.

Не смешивать это с уже готовым клиентским ботом.

## Позже ⬜

- billing/subscriptions;
- административная SaaS-панель;
- более глубокие отчёты/рекомендации;
- Google Calendar, если останется продуктовая необходимость;
- merge дублей клиенток;
- дальнейшая автоматизация поддержки.

## Ближайший порядок

1. Завершить production acceptance текущих mobile fixes (#323 и связанные регрессии).
2. Закрыть уже фактически выполненные старые client/runtime issues; #282/#284 оставить до полного исходного acceptance.
3. Устранить оставшийся web tech debt (#252/#268 по реальному scope).
4. Включить repository protection для `main` (#316).
5. После стабилизации — проектировать self-service SaaS onboarding (#223), не возвращаясь к single-master client architecture.
