# WEB-001A — Telegram challenge и server-side session

Дата: 17 июля 2026 года.

Связанные источники:

- issue #109;
- ADR-005;
- `docs/plans/WEB-001-implementation-plan.md`;
- `docs/operations/engineering-principles.md`.

## Цель

Добавить отдельную browser-facing identity boundary для web-интерфейса мастера. Браузер никогда не получает internal API key, trusted Telegram identity или owner id.

## Граница доверия

```text
Browser
  -> HTTPS reverse proxy
  -> FastAPI web routes
  -> server-side challenge/session service
  -> trusted User record
  -> RequestIdentity, сформированный сервером
  -> существующие owner-scoped domain services
```

Текущий dependency `require_request_identity`, основанный на server-to-server заголовках, сохраняется для Hermes/internal API и не используется браузером.

## Модели данных

### WebLoginChallenge

- `id: UUID` — публичный непрозрачный идентификатор;
- `secret_hash: bytes/string` — только хэш одноразового секрета;
- `requested_account_hash: bytes/string | null` — нормализованное значение, если login начинается с идентификатора; в ответах не раскрывается;
- `user_id: UUID | null` — заполняется только для активного master, но внешняя реакция одинакова для известных и неизвестных;
- `status: pending | approved | consumed | expired | locked | denied`;
- `attempt_count`;
- `max_attempts`;
- `created_at`, `expires_at`, `approved_at`, `consumed_at`;
- `request_ip_hash`;
- `user_agent_hash | null`;
- `request_id`.

Секрет challenge не хранится открытым текстом и не попадает в логи, audit `safe_changes` или URL query.

### WebSession

- `id: UUID` — внутренний идентификатор;
- `token_hash` — хэш случайного cookie token;
- `user_id`;
- `created_at`;
- `last_seen_at`;
- `idle_expires_at`;
- `absolute_expires_at`;
- `revoked_at | null`;
- `rotation_counter`;
- `created_ip_hash`;
- `last_ip_hash`;
- `user_agent_hash | null`;
- `request_id`.

В cookie хранится только случайный bearer token. Сессия целиком серверная.

## State machine challenge

```text
start
  -> pending
pending
  -> approved    trusted Telegram confirmation
  -> denied      explicit denial
  -> locked      attempt limit exceeded
  -> expired     TTL elapsed
approved
  -> consumed    successful session issuance
  -> expired     TTL elapsed before consumption
consumed/denied/locked/expired
  -> terminal
```

Переход `approved -> consumed` выполняется атомарно вместе с созданием сессии. Повторное потребление невозможно.

## Login flow

1. `POST /web/api/auth/challenges` создаёт challenge и возвращает одинаковый generic response независимо от существования аккаунта.
2. Для активного `master` сервер инициирует доставку подтверждения через доверенный Telegram transport boundary.
3. Telegram callback/action содержит непрозрачный challenge id и одноразовый секрет либо подписанную server-side action reference.
4. Подтверждение сверяется с trusted Telegram user id, найденным сервером из callback context.
5. Browser опрашивает `GET /web/api/auth/challenges/{id}` либо вызывает consume endpoint.
6. После `approved` сервер атомарно создаёт session, помечает challenge `consumed`, устанавливает cookie и возвращает authenticated state.
7. Session id/token ротируется при успешном входе. Существующий анонимный token не повышается до authenticated session.

## Внешние ответы и защита от enumeration

Для известного, неизвестного, inactive и неподходящей роли ответ на старт challenge одинаков по HTTP status, форме и пользовательской microcopy.

Не гарантируется идентичное сетевое время до наносекунд, но код не должен иметь очевидных веток ответа, раскрывающих allowlist/account existence.

## TTL и лимиты

Начальные значения для реализации и тестов:

- challenge TTL: 10 минут;
- challenge max verification attempts: 5;
- один активный challenge на browser fingerprint/account scope; новый инвалидирует старый;
- session idle TTL: 12 часов;
- session absolute TTL: 7 суток;
- touch `last_seen_at` не чаще одного раза в 5 минут;
- rate limit start challenge: 5 запросов за 15 минут на IP scope;
- дополнительный account scope: 5 за 15 минут;
- verify/consume: 10 запросов за 10 минут на challenge + IP scope;
- после превышения — generic `429` без раскрытия account state.

Все значения задаются validated environment settings с безопасными defaults и верхними/нижними границами.

## Telegram delivery boundary

WEB-001A не расширяет Telegram tool whitelist и не даёт browser доступ к Hermes.

Нужен узкий server-side adapter:

```text
Auth service -> TelegramChallengeDelivery.send_approval_request(...)
```

Контракт adapter:

- принимает только internal user id, challenge reference и безопасный display context;
- сам резолвит trusted Telegram destination server-side;
- не принимает chat/user id из browser request;
- не логирует secret, token или destination id;
- failure delivery не меняет generic browser response;
- повторная доставка идемпотентна в пределах challenge.

Конкретный transport может быть реализован через существующий закрытый bot runtime или отдельный минимальный server-side Telegram sender, но только после production inventory подтверждения доступа к token без копирования секрета в browser/backend logs.

## Session cookie

- имя с префиксом продукта, например `__Host-nails_session` при совместимой схеме публикации;
- `Secure`;
- `HttpOnly`;
- `SameSite=Lax` или `Strict`, если UX не требует другого;
- `Path=/`;
- без `Domain` для host-only cookie;
- короткое значение, достаточная энтропия не менее 256 бит;
- cookie очищается при logout, expiry и invalid session.

## Web identity dependency

Новый `require_web_session_identity`:

1. читает cookie;
2. хэширует token;
3. находит незавершённую и неистёкшую session;
4. повторно проверяет `User.is_active` и роль `master`;
5. формирует `RequestIdentity` только сервером;
6. не принимает owner id, role или Telegram id из request body/header/query;
7. обновляет idle activity с throttling;
8. возвращает generic 401 для отсутствующей, revoked и expired session.

Admin-доступ не включается автоматически в WEB-001A.

## Logout и revoke

- `POST /web/api/auth/logout` требует session и CSRF;
- ставит `revoked_at`, очищает cookie, повторный logout идемпотентен;
- смена `User.is_active` на false немедленно блокирует следующий запрос даже до очистки session;
- служебный revoke всех session пользователя предусматривается в service layer, но admin UI не входит в slice.

## CSRF, Origin и Host

CSRF contract вводится сразу:

- state-changing web endpoints принимают только same-origin requests;
- проверяются allowlisted `Host` и `Origin`;
- для form/API mutations используется synchronizer token или double-submit contract с server-side binding;
- challenge start, consume и logout считаются state-changing;
- CORS для сторонних origins не включается;
- GET endpoints не меняют persistent auth state, кроме ограниченного session activity touch.

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

В audit/logs запрещены:

- challenge secret/OTP;
- cookie token или token hash;
- internal API key;
- Telegram/chat identifiers;
- private client fields;
- полный IP и полный User-Agent.

IP/User-Agent при необходимости хранятся только в keyed hash/усечённой безопасной форме.

## Конкурентность и атомарность

- approve/deny/consume используют row lock или conditional update;
- только один consume выигрывает;
- session creation и challenge consumption — одна транзакция;
- повторная Telegram confirmation терминального challenge безопасно игнорируется;
- cleanup job переводит pending/approved challenge в expired и удаляет старые terminal rows по retention policy;
- revoke конкурирует безопасно с active request: каждый request заново валидирует session state.

## Миграции и backup

Нужна одна Alembic migration для challenge/session tables, индексов и constraints. Таблицы входят в существующий backup/restore row-count contract. Секретов в plaintext в БД нет.

## Обязательные threat-model tests

1. account enumeration: одинаковые start responses для active, inactive, unknown и wrong role;
2. plaintext challenge отсутствует в БД, logs и audit;
3. challenge нельзя consume дважды;
4. challenge нельзя approve/consume после TTL;
5. attempt limit переводит challenge в locked;
6. IP и account rate limits независимы и проверены;
7. Telegram confirmation другого user не одобряет challenge;
8. browser-supplied Telegram id, role и owner игнорируются/отклоняются;
9. session fixation исключена новым token после login;
10. stolen старый/rotated token не работает;
11. idle и absolute expiry проверяются отдельно;
12. logout и service revoke прекращают доступ;
13. inactive user блокируется при следующем request;
14. CSRF/Origin/Host negative tests;
15. cookie flags проверяются contract test;
16. concurrent consume создаёт ровно одну session;
17. owner identity в `RequestIdentity` всегда получена из session user;
18. sensitive values не появляются в captured logs.

## Не входит

- day/week API;
- frontend;
- reverse proxy deployment;
- web-мутации booking/availability/client/service;
- admin/multi-master;
- клиентский контур.

## Реализация после принятия design PR

Рекомендуемый один implementation PR WEB-001A включает:

- models + migration;
- settings;
- auth services и web routes;
- Telegram delivery interface с тестовым fake adapter;
- production adapter только при подтверждённом безопасном transport boundary;
- unit/integration/security tests;
- обновление backup/schema contracts;
- без frontend и публичного reverse proxy.
