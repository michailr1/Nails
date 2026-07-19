# Nails — текущий контекст

Дата фиксации: **20 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Базовое состояние

```text
repository: michailr1/Nails
GitHub main: 9ab6d3e8d7c8cf8f97a1c45cc7c4a7d1c1d546b3
production host: de.funti.cc
production repo: /opt/nails/repo
production branch: main
production SHA: 74346e902f2ff87e30cf967b52a26c16cc556f88
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
health: /health
readiness: /ready
timezone: Europe/Moscow
Hermes plugins: nails-onboarding, nails-scheduling
```

`main` опережает production только docs-коммитом; runtime-код production соответствует завершённому ADR-007 Slice E.

Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и fast-forward. VPS-агент только выполняет утверждённые deployment-команды.

Обязательные правила:

- один живой Telegram-тест за раз;
- роли только `master`, `admin`, `client` на уровне продуктового контракта; текущая backend enum пользователей содержит `master` и `admin`;
- имя помощника — «Нэйли»;
- каждая мутация требует подтверждения;
- успех определяется только подтверждённым tool-результатом;
- релиз: PR → CI → candidate exact SHA → fast-forward того же SHA → finalize;
- deploy выполняется только через `ops/deploy/deploy.sh <exact-SHA>`.

## Завершённые этапы

ADR-007 Slice E развернут на production. Работает импорт полного каталога услуг по одному или нескольким фото прайса через существующий vision-инструмент: Нэйли показывает единую редактируемую таблицу, отдельно помечает предложенные длительности как свою оценку и применяет каталог одной подтверждённой owner-scoped batch-мутацией. Живая Telegram-проверка успешна.

WEB-001 read-only код уже реализован и смержен ранее:

- auth/session и Telegram challenge foundation — PR #113;
- read-only календарь, клиентские карточки и export — PR #114;
- frontend — PR #115;
- изолированный web edge — PR #116;
- conversational web login — PR #118.

## WEB-001E: установленный root cause ручного входа

Synthetic challenge flow проходил, но ручная проверка выполнялась из Telegram-аккаунта, который production связывает с активным пользователем роли `admin`, а не `master`.

Факты диагностики:

- trusted Telegram identity до backend доходит корректно;
- internal API key, HMAC namespace и runtime совпадают;
- pending challenge существует;
- `require_web_approval_identity()` намеренно разрешает только активную роль `master`;
- ADR-005 оставляет admin/multi-master для отдельного позднего gated slice;
- ответ `not_found` для admin является ожидаемым fail-closed поведением, а не поломкой поиска challenge.

Устаревший incident PR #119 закрыт без merge. Дублирующий issue #146 о повторной реализации read-only календаря закрыт как duplicate.

## Следующий приоритет

1. Провести одну живую browser + Telegram acceptance из активного Telegram-аккаунта мастера.
2. После успешного входа не переписывать read-only календарь, а проверить уже существующий web UI на production.
3. Первый новый write-slice: web-редактор каталога услуг с mutation-CSRF, idempotency, preview, server-side validation и fresh readback.
4. Затем web-редактор графика, карточек клиенток и управление записями.

## Точка продолжения

```text
1. live web login acceptance from active master Telegram account
2. verify existing read-only calendar/client UI
3. open service-catalog web write slice
4. implement mutation-CSRF before any domain write
```
