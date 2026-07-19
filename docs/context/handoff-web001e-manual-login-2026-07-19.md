# Nails — handoff WEB-001E manual login incident

Дата: 19 июля 2026 года.

## Источник истины

Перед работой прочитать:

- `AGENTS.md`;
- `docs/context/current.md`;
- `docs/operations/engineering-principles.md`;
- production/deploy operational docs;
- ADR-005 и ADR-006;
- `docs/design/lovable-web-baseline.md`;
- `docs/plans/WEB-001-implementation-plan.md`.

Не полагаться на этот handoff как на замену фактической проверке GitHub и production.

## Репозиторий и production

```text
repository: michailr1/Nails
GitHub main: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
production host: de.funti.cc
production repo: /opt/nails/repo
production HEAD: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
runtime API SHA: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
runtime WEB SHA: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
working tree: clean
internal API: 127.0.0.1:8210
public WEB: https://de.funti.cc:8446/web/
health: true
readiness: true
public API hidden: true
web_login tool enabled: true
gateway active: true
data counts: services=4, clients=7, bookings=15
```

## Release fact

PR #118 `feat: WEB-001E conversational web login`:

```text
base: 88785eae176e9b8a6556f592ca8bc63c35cda735
exact head: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
merge method: fast-forward main to exact head
candidate runtime: exact head
finalize: successful
FINALIZE_OK=true
```

Feature flag `NAILS_WEB_LOGIN_TOOL_ENABLED=true` установлен в активном Nails profile env. Backup на VPS:

```text
/root/.hermes/profiles/nails/backups/web-login-flag-20260718T223010Z.env
```

Не печатать содержимое profile env или backup.

## Реализованный flow

- Browser создаёт challenge через `POST /web/api/auth/challenges`.
- Показывает шестизначное число.
- Мастер пишет Нэйли: `подтверди вход 123456`.
- Hermes restricted `web_login` tool использует trusted Telegram context.
- Lookup: `GET /api/v1/web-auth/conversation/challenge?verification_number=...`.
- Decision: `POST /api/v1/web-auth/conversation/decision` с `decision=approve|deny`.
- Browser polling: `GET /web/api/auth/challenges/{challenge_id}`.
- Consume: `POST /web/api/auth/challenges/consume`.
- Создаётся server-side session.

## Что подтвердил synthetic acceptance

```text
challenge create: 201
lookup: pending
approve: approved
browser status: approved
consume: authenticated=true, status=consumed
wrong master lookup/decision: not_found
expired: expired
repeated approve: approved
browser deny status: denied
browser copy: true
data unchanged: true
```

Production rate-limit был многократно задет диагностическими challenge-create; это объясняло часть 429, но не ручной дефект.

## Фактический пользовательский инцидент

Ручной механизм не работает.

Пользователь несколько раз:

1. создавал новый код в WEB;
2. сразу отправлял его Нэйли;
3. получал ответ: `Код <number> не найден или уже истёк, поэтому подтвердить его нельзя.`

Скриншоты были сделаны позже, но lookup выполнялся сразу. Версия про истечение отвергнута пользователем и не должна повторяться.

Итог:

```text
WEB-001E deployed=true
synthetic_acceptance=true
manual_acceptance=false
user_visible_login_works=false
```

## Основная гипотеза

Synthetic flow проверял backend API с тестовыми identity headers, но не доказал реальную binding-цепочку:

```text
HERMES_SESSION_PLATFORM / HERMES_SESSION_USER_ID
  -> trusted Telegram user id
  -> users.telegram_user_id
  -> users.id
  -> web_login_challenges.owner_user_id
```

Возможен mismatch реального Telegram identity и owner scope challenge.

## Следующая операция: только read-only diagnostic

Нельзя сразу менять код или данные. Сначала на `de.funti.cc` определить:

- последние реальные challenge безопасными полями: short id, timestamps, status, owner_user_id, approved_by_user_id, consumed/denied timestamps, наличие hashes без их значений;
- активных master users: internal id, telegram_user_id, role, is_active;
- фактический trusted Telegram ID последнего вызова web_login;
- соответствие trusted ID → user → challenge owner;
- существовал ли global hash match и owner-scoped match;
- pending/expired/rate-limited state в момент lookup;
- совпадают ли API/Hermes internal key без вывода значения;
- configured ли WEB_AUTH_HMAC_KEY;
- одинаковы ли hash algorithm и namespace create/lookup;
- clock skew host/API/DB;
- вызывает ли Hermes текущий endpoint/runtime.

Root-cause classification:

```text
A. trusted Telegram ID не соответствует owner_user_id
B. challenge создаётся без корректного owner_user_id
C. create и lookup используют разные key/namespace
D. challenge преждевременно expired/denied
E. lookup блокируется rate limit
F. Hermes вызывает не тот endpoint/runtime
G. недостаточно диагностических данных
```

## Ограничения диагностики

- не менять GitHub, checkout, runtime, config или БД;
- не создавать challenges;
- не очищать rate limits;
- не перезапускать сервисы;
- не выводить verification numbers, hashes, HMAC, API keys, cookies, tokens, `.env`, DATABASE_URL;
- domain data не менять.

## После root cause

Исправление оформить отдельным PR. Обязательный regression test должен покрывать реальную identity binding, а candidate acceptance должен включать живой Telegram round-trip конкретного master account. До успешного ручного входа не переходить к read-only calendar.
