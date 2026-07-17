# Nails — текущий контекст для продолжения работы

Дата фиксации: **17 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/operations/engineering-principles.md`, остальные operational-документы, ADR-005, ADR-006, `docs/design/lovable-web-baseline.md` и `docs/plans/WEB-001-implementation-plan.md`.

Не полагаться на память: GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Рабочий контракт

```text
repository: michailr1/Nails
GitHub main: 11dd79d6a8d7dfecd2beb5211b98e73c91e96e0d
production host: de.funti.cc
production repo: /opt/nails/repo
production branch: main
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
health: /health
readiness: /ready
timezone: Europe/Moscow
Hermes plugins: nails-onboarding, nails-scheduling
```

Основной агент пишет код, тесты и документацию, управляет GitHub, review, CI и fast-forward merge. VPS-агент только выполняет утверждённый runbook и не меняет код или GitHub.

Обязательные правила:

- один живой Telegram-тест за раз;
- в GitHub используются только роли `master`, `admin`, `client`, без персональных имён;
- имя интерфейса и помощника — «Нэйли».

Релизы выполняются постоянным `ops/deploy/deploy.sh <exact-SHA>` по схеме PR → CI → candidate exact SHA → fast-forward того же SHA → finalize.

## Production milestone

```text
production backend SHA: 847a6342911b5bf32a9e6c0885065e161c6d2d06
ADR-006: accepted and deployed
API bind: 127.0.0.1:8210
health: ok
readiness: ok
gateway: active
```

Документационные коммиты после production SHA deployment не требовали.

## Завершено

- NAILS-002F;
- NAILS-003 и issue #104;
- ADR-006;
- ADR-005, PR #108;
- Lovable baseline, PR #110.

Клиентский контур начинается только после web-интерфейса.

## ADR-006

Availability intervals и диапазон 10:00–23:00 являются подсказками. Явно названное время открыто по умолчанию. Отказ допускается только для целого выходного или конфликта с активной записью с учётом buffers.

## Текущая задача

Issue #109 — WEB-001: Telegram auth, server-side session и read-only calendar.

Принятый стек:

```text
Browser
  -> HTTPS reverse proxy на высоком нестандартном порту
  -> React + Vite frontend
  -> существующий FastAPI как web/BFF
  -> существующие owner-scoped services
  -> PostgreSQL
```

Внутренний API остаётся loopback-only. Lovable используется как визуальный baseline; его runtime и служебный scaffold целиком не переносятся.

## Инвентаризация

Переиспользуются User, RequestIdentity как внутренний тип, owner-scoped scheduling services, get_day_view, presenters, AuditEvent, APP_TIMEZONE, Alembic, backup/restore и deploy contracts.

Нужны новые web-specific механизмы входа и сессий, week read model, booking detail read model, frontend contract и edge deployment.

## Разбиение

Источник истины: `docs/plans/WEB-001-implementation-plan.md`.

```text
WEB-001A: login challenge и server-side session
WEB-001B: read-only day/week/appointment API
WEB-001C: React + Vite frontend
WEB-001D: reverse proxy, deployment и acceptance
```

Порядок: A → B → C → D.

## Ограничения

- без внешнего auth/backend;
- не выставлять internal API наружу;
- не дублировать booking logic;
- не доверять identity или owner из browser;
- не начинать web-мутации, admin, export или клиентский контур;
- не создавать одноразовые deploy scripts;
- production compose запускать с `--env-file /opt/nails/.env`;
- readiness проверять через `/ready`.

## Точка продолжения

```text
1. принять документационный PR без production deploy
2. начать отдельный design/review PR WEB-001A
3. зафиксировать модели challenge/session, state machine, TTL и rate limits
4. зафиксировать Telegram delivery boundary и threat-model tests
5. после review начать реализацию WEB-001A
```
