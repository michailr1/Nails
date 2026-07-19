# Nails — текущий контекст для продолжения работы

Дата фиксации: **19 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/operations/engineering-principles.md`, operational-документы, ADR-005, ADR-006, `docs/design/lovable-web-baseline.md` и `docs/plans/WEB-001-implementation-plan.md`.

Не полагаться на память: GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Рабочий контракт

```text
repository: michailr1/Nails
GitHub main: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
production host: de.funti.cc
production repo: /opt/nails/repo
production branch: main
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
health: /health
readiness: /ready
timezone: Europe/Moscow
Hermes plugins: nails-onboarding, nails-scheduling
public WEB: https://de.funti.cc:8446/web/
```

Основной агент пишет код, тесты и документацию, управляет GitHub, review, CI и fast-forward merge. VPS-агент только выполняет утверждённый runbook и не меняет код или GitHub.

Обязательные правила:

- один живой Telegram-тест за раз;
- в GitHub используются только роли `master`, `admin`, `client`, без персональных имён;
- имя интерфейса и помощника — «Нэйли»;
- внутренний Booking API остаётся loopback-only;
- browser работает через same-origin WEB/BFF;
- не выводить secrets, HMAC, cookies, токены, `.env` и `DATABASE_URL`.

Релизы выполняются постоянным `ops/deploy/deploy.sh <exact-SHA>` по схеме PR → CI → candidate exact SHA → fast-forward того же SHA → finalize.

## Production milestone

```text
GitHub main: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
production HEAD: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
runtime API SHA: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
runtime WEB SHA: c258823dfa51ff36a4df0f1485c2a150bb0cb23e
working tree: clean
API bind: 127.0.0.1:8210
health: ok
readiness: ok
WEB public: ok
/web redirect: 308 -> /web/
public API: hidden
web_login tool: enabled
gateway: active
domain data counts: services=4, clients=7, bookings=15
```

PR #118 / WEB-001E был fast-forward merged и finalized на production.

## Завершено

- NAILS-002F;
- NAILS-003 и issue #104;
- ADR-006;
- ADR-005, PR #108;
- Lovable baseline, PR #110;
- WEB-001E implementation, PR #118, production finalize.

Клиентский контур начинается только после web-интерфейса.

## WEB-001E — фактический статус

Реализован master-initiated вход по шестизначному числу:

```text
browser creates challenge
master sends: «подтверди вход 123456»
Hermes web_login tool reads owner-scoped pending challenge
master separately approves or denies
browser polls status and consumes approved challenge
server-side session is created
```

Synthetic acceptance подтвердил:

- create challenge;
- lookup `pending`;
- approve `approved`;
- browser status `approved`;
- consume `authenticated=true`, `status=consumed`;
- wrong-master isolation `not_found`;
- expiry;
- repeated approve idempotency;
- deny browser status `denied`;
- browser copy;
- domain data unchanged.

## Критический открытый инцидент

**Ручной production login не работает.**

Пользователь несколько раз создавал новый код в браузере и сразу отправлял его Нэйли. Нэйли отвечала: «Код не найден или уже истёк». Это не задержка и не истечение кода.

Следовательно, WEB-001E нельзя считать пользовательски принятым, несмотря на успешный synthetic acceptance и finalize.

Наиболее вероятная зона дефекта — реальная identity-интеграция:

```text
Hermes trusted Telegram user id
  -> users.telegram_user_id
  -> users.id
  -> web_login_challenges.owner_user_id
```

Также проверить:

- challenge действительно существует и pending в момент lookup;
- одинаковые keyed-hash key/namespace у create и lookup;
- Hermes вызывает текущий endpoint/runtime;
- нет rate-limit или clock-skew;
- challenge не создаётся без корректного owner scope.

## Следующая задача

Сначала выполнить **read-only production diagnostic** реального ручного входа. Не начинать read-only calendar до нахождения и исправления причины.

Классификация root cause:

```text
A. trusted Telegram ID не соответствует owner_user_id
B. challenge создаётся без корректного owner_user_id
C. create и lookup используют разные key/namespace
D. challenge преждевременно expired/denied
E. lookup блокируется rate limit
F. Hermes вызывает не тот endpoint/runtime
G. диагностических данных недостаточно
```

## Точка продолжения

```text
1. проверить фактический main и production SHA
2. выполнить утверждённую read-only диагностику ручного WEB-001E login
3. сопоставить trusted Telegram ID, user id и challenge owner_user_id
4. определить одну root-cause class A-G
5. исправление делать отдельным PR с regression test реальной identity binding
6. candidate должен включать ручной Telegram acceptance, а не только synthetic API checks
7. только после успешного ручного входа продолжать WEB-001 read-only calendar
```
