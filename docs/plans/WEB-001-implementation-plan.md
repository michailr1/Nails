# WEB-001 — implementation plan

Дата: 17 июля 2026 года.

Связанные источники:

- issue #109;
- ADR-005;
- ADR-006;
- `docs/design/lovable-web-baseline.md`;
- `docs/operations/engineering-principles.md`.

## Цель

Реализовать первый gated web-slice: безопасный вход мастера через Telegram, server-side session и read-only календарь без web-мутаций.

## Принятый стек

```text
Browser
  -> HTTPS reverse proxy на выделенном высоком нестандартном порту
  -> React + Vite static frontend
  -> существующий FastAPI как web/BFF
  -> существующие owner-scoped domain services
  -> PostgreSQL
```

Высокий порт не является security boundary. Реальные controls: TLS, auth, server-side sessions, rate limiting, CSRF, Origin/Host validation и owner isolation.

TanStack Start runtime Lovable, generated router, mock auth, prototype switcher и Lovable reporting в production не переносятся.

## Что переиспользуется

- `User.telegram_user_id`, `User.role`, `User.is_active`;
- `RequestIdentity` как внутренний тип доверенной identity, но не текущий header dependency для browser requests;
- owner-scoped scheduling services;
- `get_day_view`;
- существующие booking/client/service presenters;
- `AuditEvent`;
- `APP_TIMEZONE`;
- PostgreSQL, Alembic, backup/restore contract;
- постоянный `ops/deploy/deploy.sh`.

## Что отсутствует

- login challenge storage;
- server-side session storage;
- browser-safe session identity dependency;
- logout/revoke;
- rate-limit persistence/contract;
- week read model;
- отдельный booking detail read model;
- public web service и reverse-proxy configuration;
- frontend build/test/deploy contract.

## Security boundary

- Browser никогда не получает `INTERNAL_API_KEY`.
- Browser не передаёт trusted Telegram identity, user id или owner id.
- Текущий `require_request_identity`, основанный на `X-Nails-Internal-Key` и `X-Telegram-User-ID`, остаётся только server-to-server boundary.
- Web session после успешного challenge резолвит `User` на сервере и формирует identity исключительно из server-side session.
- Неизвестный и неактивный пользователь получает неразличимый внешний ответ.
- Cookie: `Secure`, `HttpOnly`, `SameSite=Lax` или строже.
- Session id ротируется после входа; действуют idle и absolute TTL.
- Challenge одноразовый, короткоживущий, ограниченный по попыткам и не логируется.
- CSRF contract, Host/Origin validation и закрытый CORS вводятся с первого slice.
- Логи не содержат cookie, challenge/OTP, internal key и private client content.

## WEB-001A — challenge и server-side session

Состав:

- миграции challenge/session;
- безопасное хранение challenge verifier/digest;
- start/confirm/status flow;
- Telegram delivery через существующий доверенный bot transport без расширения restricted toolset;
- rate limiting;
- session rotation, idle/absolute TTL;
- logout и revoke;
- web-session identity dependency;
- audit без секретов;
- unit/integration/security tests.

Не включает календарный UI.

## WEB-001B — read-only web API

Состав:

- web day endpoint поверх `get_day_view`;
- week endpoint как композиция существующего owner-scoped day query либо общий range-query без дублирования правил;
- booking detail endpoint;
- только scheduled bookings в основном календаре;
- cancelled не показываются по умолчанию;
- production timezone;
- DTO без лишних private fields;
- owner-isolation regression tests.

Разрешённые поля первого slice:

- booking id;
- client display name;
- start/end datetime;
- service name;
- duration;
- price snapshot;
- доступные private notes мастера;
- status.

Не добавлять Telegram клиента, историю визитов и выдуманные поля.

## WEB-001C — frontend

Состав:

- React + Vite;
- визуальный baseline из `docs/design/lovable-web-baseline.md`;
- login и ожидание Telegram confirmation;
- day/week calendar;
- read-only booking detail;
- loading, empty, network error, expired session и access denied;
- mobile-first layout и desktop rail;
- русский язык;
- без create/edit/cancel controls;
- API client отделён от UI.

## WEB-001D — edge и production acceptance

Состав:

- отдельный web container/service;
- HTTPS reverse proxy на утверждённом высоком порту;
- internal API остаётся `127.0.0.1:8210`;
- secure headers и request-size/time limits;
- health/readiness для web surface;
- обновление постоянного deploy script, без одноразовых scripts;
- candidate exact SHA;
- fast-forward того же SHA;
- auth/session/owner-isolation/calendar acceptance;
- обновление roadmap, status и current context.

## Порядок

```text
WEB-001A -> WEB-001B -> WEB-001C -> WEB-001D
```

Каждый slice проходит отдельный PR и зелёный CI. Production deployment требуется только там, где нужен реальный runtime acceptance.

## Запреты

- не подключать Supabase или внешний auth/backend;
- не выставлять internal API наружу;
- не дублировать booking business logic;
- не доверять identity/owner из браузера;
- не начинать web-мутации, admin/multi-master, export или клиентский контур;
- не переносить Lovable scaffold целиком;
- не создавать одноразовые deploy/install scripts.

## Следующая точка

Начать WEB-001A с отдельного design/review PR, включающего точные модели challenge/session, state machine, TTL, rate-limit contract, Telegram delivery boundary и threat-model tests. Реализацию не смешивать с frontend.