# Lovable web baseline для WEB-001

Дата фиксации: 17 июля 2026 года.

## Источник

- Lovable project: `Nails UX Blueprint`
- Project ID: `08982064-17a5-4ed2-b809-c37da6161ef2`
- Final Lovable commit: `ff66d4165b3a24cfea6d35393366f5bb9de6de5d`
- Project visibility: private
- Published: no
- Database/Supabase: not enabled
- Backend/API integration: none
- Real Telegram auth: none; only mock interaction

Lovable использован только для формирования UX/UI baseline. Его TanStack Start runtime, generated router и служебные файлы не являются автоматически принятой production-архитектурой Nails.

## Что принято

- визуальный стиль «Нэйли»;
- mobile-first компоновка;
- desktop rail и адаптивная недельная сетка;
- экран входа через Telegram;
- экран ожидания подтверждения;
- read-only день и неделя;
- read-only карточка записи;
- состояния loading, empty, network error, expired session и access denied;
- отдельный prototype state switcher только для дизайн-ревью;
- русская microcopy;
- отсутствие ложных create/edit/cancel действий в первом slice.

## Принятые маршруты

```text
/
/login
/login/confirm
/today
/day/:date
/week/:isoWeek
/appointment/:id
/session-expired
/access-denied
/offline
```

Production router может отличаться технически, но пользовательские состояния и переходы сохраняются.

## Основные компоненты baseline

```text
AppShell
ReadOnlyBadge
AppointmentListItem
StatusDot
DateStrip
DayTimeline
NowMarker
EmptyState
SkeletonList
NetworkErrorBanner
FullscreenState
TelegramIcon
PrototypeStateSwitcher  # prototype-only
```

## Реальная модель данных первого slice

UI должен принимать только поля, существующие в backend contract:

```text
booking_id
client_display_name
start_at
end_at
service_name_snapshot
price_snapshot
private_notes       # только master-only, когда поле реально доступно
status              # scheduled | cancelled
```

Длительность вычисляется из `start_at` и `end_at` либо берётся из авторитетного backend response, если контракт явно её возвращает.

Запрещено выдумывать для первого slice:

- Telegram клиента;
- историю визитов;
- телефон, если он не возвращён конкретным master-only endpoint;
- финансовую аналитику;
- новые статусы записи;
- параллельную модель availability.

Отменённые записи не показываются в основном календаре по умолчанию.

## Design tokens

### Типографика

```text
Display: Fraunces
UI/body: Inter Tight
Time/numbers: tabular numerals
```

В production разрешается заменить внешнюю загрузку Google Fonts на локально допустимый или системный fallback. Внешний font CDN не является обязательной частью baseline.

### Цветовая семантика

```text
background: warm porcelain
foreground: warm graphite
card: near-white warm surface
muted: warm grey-beige
primary: muted dusty rose
accent: restrained burgundy
success: muted sage
warning: muted amber
error/destructive: muted terracotta
```

Токены задаются семантически; компоненты не должны содержать произвольные product colors вне token layer.

### Радиусы и размеры

```text
radius-sm: 8px
radius-md: 12px
radius-lg: 16px
radius-xl: 20px
minimum touch target: 44px
mobile baseline: 360–430px
desktop breakpoint: approximately 1024px
```

## Принятые UX-правила

1. После входа открывается «Сегодня».
2. Часовой пояс определяется server-side профилем мастера; текущий production default — `Europe/Moscow`.
3. Первый день недели — понедельник.
4. Рабочая визуальная шкала — `10:00–23:00`, но фактическая запись вне диапазона всё равно отображается.
5. ADR-006 действует без изменений: availability intervals — подсказки, а не жёсткие частичные запреты.
6. Карточка записи честно read-only.
7. Prototype state switcher не попадает в production build.
8. Mock-кнопка «Я подтвердил в Telegram» заменяется реальным polling/consume flow и не сохраняется в production.
9. Internal API key, Telegram identity и owner id никогда не попадают в browser runtime.
10. Ошибка сети с ранее загруженными данными показывается inline; без данных — полноэкранным состоянием.

## Что не переносится из Lovable автоматически

- весь template project;
- `.lovable/*`;
- generated `routeTree.gen.ts` как источник истины;
- Lovable error reporting;
- mock data и фиксированное `TODAY_ISO`;
- simulated current time;
- prototype state provider/switcher в production;
- внешний Google Fonts dependency без отдельного решения;
- TanStack Start как уже принятое архитектурное решение;
- любые Supabase или Lovable hosting integrations.

## План самостоятельного переноса

1. Выполнить read-only inventory фактического `main` по issue #109.
2. Выбрать минимальный web runtime и BFF boundary, совместимые с FastAPI deployment и ADR-005.
3. Создать frontend shell и semantic token layer.
4. Перенести визуальные компоненты без mock auth и prototype utilities.
5. Сформировать typed API contract для read-only day/week booking views.
6. Реализовать Telegram challenge и server-side session отдельно от UI.
7. Добавить owner-isolation, auth/session, CSRF/Origin/Host и log-redaction tests.
8. Провести candidate deployment на точном SHA и отдельную production acceptance.

## Acceptance визуального переноса

- login/confirm/day/week/appointment/system states визуально соответствуют baseline;
- mobile и desktop работают без горизонтального overflow;
- интерфейс остаётся полностью read-only;
- отсутствуют Supabase, Lovable runtime и mock-only controls;
- browser bundle не содержит секретов и trusted identity fields;
- данные приходят только из owner-scoped BFF endpoints;
- private notes отображаются только в разрешённом master-only contract.
