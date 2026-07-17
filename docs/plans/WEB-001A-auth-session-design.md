# WEB-001A — Telegram challenge и server-side session

Дата: 17 июля 2026 года.

Связанные источники:

- issue #109;
- ADR-005;
- `docs/plans/WEB-001-implementation-plan.md`;
- `docs/operations/engineering-principles.md`.

## Цель

Добавить browser-facing identity boundary для web-интерфейса мастера. Браузер никогда не получает internal API key, trusted Telegram identity или owner id.

## Принятый login flow

```text
Browser
  -> создаёт анонимный challenge
  -> показывает короткий код и действие «Открыть Telegram»
Master
  -> отправляет или подтверждает код в закрытом боте
Hermes/bot runtime
  -> передаёт challenge code + trusted Telegram identity во внутренний API
Backend
  -> одобряет challenge для активного master
Browser
  -> consume challenge
  -> получает server-side session cookie
```

Старт challenge не принимает Telegram ID, username, телефон, owner id или другой account identifier. Поэтому он не выполняет account lookup и не раскрывает наличие пользователя.

Backend не получает Telegram bot token. Доставка исходящего сообщения не требуется для основного flow: пользователь сам открывает уже существующего закрытого бота. Допустима только безопасная deep link или инструкция, не содержащая секрета в URL.

## Граница доверия

```text
Browser
  -> HTTPS reverse proxy
  -> FastAPI web routes
  -> challenge/session service
  -> trusted User record
  -> RequestIdentity, сформированный сервером
  -> существующие owner-scoped domain services

Hermes/bot runtime
  -> internal API с существующим internal key
  -> trusted Telegram identity из Telegram update context
  -> challenge approval service
```

Текущий `require_request_identity`, основанный на server-to-server заголовках, сохраняется для Hermes/internal API. Browser его не использует.

## Модели данных

### WebLoginChallenge

- `id: UUID` — публичный непрозрачный идентификатор browser polling;
- `code_hash` — keyed hash короткого одноразового кода;
- `status: pending | approved | consumed | expired | locked | denied`;
- `approved_user_id: UUID | null`;
- `attempt_count`, `max_attempts`;
- `created_at`, `expires_at`, `approved_at`, `consumed_at`;
- `request_ip_hash`;
- `user_agent_hash | null`;
- `request_id`.

Открытый код существует только в response создания challenge и пользовательском интерфейсе. В БД хранится keyed hash. Код не попадает в query string, logs или audit.

Короткий код должен иметь достаточную энтропию для TTL и rate limits. Рекомендуемый формат — 8 символов из однозначного alphabet без похожих знаков. UUID challenge не является секретом.

### WebSession

- `id: UUID`;
- `token_hash` — keyed hash случайного cookie token;
- `user_id`;
- `created_at`, `last_seen_at`;
- `idle_expires_at`, `absolute_expires_at`;
- `revoked_at | null`;
- `rotation_counter`;
- `created_ip_hash`, `last_ip_hash`;
- `user_agent_hash | null`;
- `request_id`.

В cookie хранится только случайный token с энтропией не менее 256 бит. Сессия целиком серверная.

## State machine challenge

```text
start -> pending
pending -> approved   trusted bot confirmation
pending -> denied     explicit bot denial
pending -> locked     attempt limit exceeded
pending -> expired    TTL elapsed
approved -> consumed  atomic session issuance
approved -> expired   TTL elapsed before consume
consumed/denied/locked/expired -> terminal
```

`approved -> consumed` и создание session выполняются в одной транзакции. Повторный consume невозможен.

## Endpoints

Browser-facing:

- `POST /web/api/auth/challenges` — создать anonymous challenge;
- `GET /web/api/auth/challenges/{id}` — получить только generic state;
- `POST /web/api/auth/challenges/{id}/consume` — создать session после approval;
- `POST /web/api/auth/logout` — revoke текущей session.

Internal bot-facing:

- отдельная узкая action/service operation `approve_web_login_challenge`;
- вход: code и trusted `RequestIdentity` от Hermes runtime;
- browser не может вызвать её через public web boundary;
- операция разрешена только активной роли `master`;
- admin не получает web-master session автоматически.

Polling response не содержит user id, Telegram identity, роль или owner data.

## Bot integration boundary

Предпочтительный вариант — новая restricted action в существующем profile-local plugin либо отдельный минимальный auth plugin, вызывающий internal API тем же доверенным способом, что текущие Nails actions.

Обязательные свойства:

- trusted Telegram identity берётся только из Telegram update context;
- пользователь вводит или подтверждает короткий code;
- plugin не хранит session cookie и не получает browser token;
- code не печатается в logs;
- Telegram tool whitelist не расширяется опасными general-purpose tools;
- повторное подтверждение терминального challenge идемпотентно;
- неизвестный, inactive или wrong-role Telegram user получает нейтральный отказ без сведений о других аккаунтах.

WEB-001A не добавляет Telegram token в backend environment и не создаёт второй polling/webhook consumer.

## TTL и лимиты

Начальные значения:

- challenge TTL: 10 минут;
- bot approval attempts: 5 на challenge;
- один pending challenge на browser scope; новый инвалидирует предыдущий;
- session idle TTL: 12 часов;
- session absolute TTL: 7 суток;
- `last_seen_at` touch не чаще одного раза в 5 минут;
- challenge start: 5 запросов за 15 минут на IP scope;
- status polling: bounded frequency, например 30 запросов за 10 минут на challenge + IP;
- bot approval: 10 запросов за 10 минут на Telegram account scope и IP/server scope;
- consume: 10 запросов за 10 минут на challenge + IP;
- превышение public limit возвращает generic `429`.

Параметры задаются validated settings с безопасными границами.

Rate limiting не должен зависеть только от process memory. Для одного production API instance допустима PostgreSQL-backed реализация; архитектура должна оставаться корректной после restart и при будущих нескольких workers.

## Session cookie

- предпочтительное имя `__Host-nails_session` при совместимой схеме публикации;
- `Secure`;
- `HttpOnly`;
- `SameSite=Lax` или строже;
- `Path=/`;
- без `Domain`;
- очищается при logout, expiry и invalid session.

## Web identity dependency

Новый `require_web_session_identity`:

1. читает cookie;
2. хэширует token;
3. находит active, non-expired session;
4. повторно проверяет `User.is_active` и роль `master`;
5. формирует `RequestIdentity` только server-side;
6. не принимает identity/owner/role из browser request;
7. обновляет idle activity с throttling;
8. возвращает generic `401` для отсутствующей, revoked и expired session.

## Logout и revoke

- logout требует session, same-origin и CSRF;
- ставит `revoked_at` и очищает cookie;
- повторный logout идемпотентен;
- inactive user блокируется при следующем request;
- service layer предусматривает revoke всех sessions пользователя без admin UI.

## CSRF, Origin и Host

- state-changing endpoints принимают только same-origin requests;
- allowlist `Host` и `Origin`;
- CSRF token server-bound;
- start, consume и logout считаются state-changing;
- сторонний CORS не включается;
- GET polling не создаёт session и не меняет challenge state;
- session activity touch — единственное допустимое ограниченное изменение на authenticated GET.

## Audit и logging

Audit actions:

- `web_login_challenge_started`;
- `web_login_challenge_approved`;
- `web_login_challenge_denied`;
- `web_login_challenge_locked`;
- `web_session_created`;
- `web_session_rotated`;
- `web_session_revoked`;
- `web_login_rate_limited`.

Запрещены в audit/logs:

- открытый code и его hash;
- cookie token и token hash;
- internal API key;
- Telegram/chat identifiers;
- private client fields;
- полный IP и полный User-Agent.

IP/User-Agent при необходимости хранятся только в keyed hash или безопасно усечённой форме.

## Конкурентность и cleanup

- approve/deny/consume используют row lock или conditional update;
- только один consume создаёт session;
- повторная bot confirmation terminal challenge безопасно игнорируется;
- cleanup переводит просроченные rows в expired и удаляет старые terminal rows по retention;
- каждый authenticated request заново валидирует session и user state;
- новый login не обязан отзывать другие sessions в MVP, но лимит active sessions на user должен быть задан и тестируем.

## Миграции и backup

Одна Alembic migration добавляет challenge/session и при необходимости rate-limit bucket tables, constraints и индексы. Новые таблицы входят в backup/restore row-count contract. Plaintext secrets в БД отсутствуют.

## Обязательные threat-model tests

1. challenge start не принимает account identity и всегда имеет одну форму ответа;
2. plaintext code отсутствует в БД, logs и audit;
3. code нельзя использовать дважды;
4. code нельзя approve/consume после TTL;
5. неверные попытки переводят challenge в locked;
6. public и bot rate limits проверены отдельно;
7. trusted Telegram identity другого пользователя связывает session только с этим пользователем, а не с browser input;
8. inactive, unknown и wrong-role Telegram user не одобряют challenge;
9. browser-supplied Telegram id, role и owner отклоняются;
10. session fixation исключена новым token;
11. rotated/revoked token не работает;
12. idle и absolute expiry независимы;
13. logout и service revoke прекращают доступ;
14. CSRF, Origin и Host negative tests;
15. cookie flags проверяются contract test;
16. concurrent consume создаёт ровно одну session;
17. `RequestIdentity.user_id` всегда получен из session user;
18. sensitive values отсутствуют в captured logs;
19. API restart не делает pending challenge или active session некорректными;
20. GET polling не создаёт session до explicit consume.

## Не входит

- day/week API;
- frontend;
- reverse proxy deployment;
- web-мутации;
- admin/multi-master;
- клиентский контур.

## Implementation PR после принятия design

Один WEB-001A implementation PR:

- models, migration и settings;
- challenge/session/rate-limit services;
- browser web routes;
- internal bot approval operation;
- restricted Hermes plugin action;
- unit, integration и security tests;
- backup/schema contract updates;
- без frontend и публичного reverse proxy.
