# Инженерные принципы — вводная для LLM-архитектора и разработчика

Дата актуализации: **20 сентября 2026 года**.

Обязательно читать вместе с `AGENTS.md`. Главный failure mode LLM-разработки здесь — добавлять новый защитный слой вместо устранения причины.

## 1. Масштаб проекта — ограничитель сложности

Nails остаётся компактным продуктом на одном VPS, но уже **не** «один мастер / один бот / два контейнера»:

- доверенный master Telegram-контур через Hermes;
- web-кабинет мастера;
- отдельный platform client Telegram bot;
- multi-master owner scoping/bindings;
- FastAPI + PostgreSQL;
- Compose runtime с API, web, DB и client bot.

Multi-master уже принят ADR-009. Это **не** разрешение строить заранее billing platform, service mesh, Kubernetes, публичный directory или микросервисную архитектуру. Новая сложность должна отвечать текущей продуктовой необходимости.

## 2. Что священно и не упрощается

- identity только из доверенного transport/server-side context;
- owner scoping;
- client не выбирает owner через body/query;
- master подтверждает mutating business actions;
- pending client request не равен Booking и не резервирует slot;
- snapshots цены/длительности;
- приватность internal client notes;
- audit/idempotency;
- backup перед mutating production deploy;
- честность: успех только после подтверждённого результата API/runtime.

## 3. Правила против разрастания

1. **Устраняй класс ошибки, а не симптом.**
2. **Переиспользуй существующий механизм до создания нового.**
3. **Никаких V2/V3-клонов файлов вместо исправления текущего.**
4. **Один постоянный production deploy path:** `ops/deploy/deploy.sh`.
5. **Candidate — изолированный adapter, не production deploy:** `ops/deploy/candidate_deploy.sh`.
6. **Source of truth — фактические refs/runtime.** Не доверять старым SHA в документах.
7. **Rollback = deploy предыдущего SHA.**
8. **Production incident начинается с identity:** source ref → built SHA → running SHA.
9. **Один факт — один нормативный источник.** Не размножать статусы по документам.
10. **Открыто по умолчанию.** Явно заданное мастером время блокируют day-off/overlap, а не отсутствие заранее заполненной сетки.
11. **Не возвращать obsolete client architecture:** никакого `CLIENT_OWNER_TELEGRAM_USER_ID`, bot-per-master или public master directory.

## 4. Release discipline

### Branch / PR

Изменения идут через branch → PR → CI. Direct push в `main` организационно запрещён; #316 должен закрепить это механически repository rules.

### Pre-merge candidate

Если изменение требует runtime acceptance, VPS проверяет exact PR-head через isolated `candidate_deploy.sh`.

Candidate обязан:

- не менять production checkout;
- не использовать production DB/env/ports;
- не пересоздавать production containers;
- не запускать client bot на production token;
- очищать собственные resources.

### Merge

PR-head candidate не считается проверкой exact merge SHA, если GitHub создал новый merge/squash/rebase commit. После merge fresh `origin/main` является новым release candidate для production.

Не требуется искусственно запрещать merge commit/squash ради тождества SHA; требуется честно различать **tree validation PR** и **exact merged release SHA**.

### Production

Production deploy выполняется только:

```bash
ops/deploy/deploy.sh <exact-main-sha>
```

после зелёного CI и необходимых acceptance checks.

## 5. Дисциплина изменений

**Перед проектированием:** найти существующие endpoints/functions/migrations/contracts, которые уже решают часть задачи.

**Неоднозначность:** если выбор влияет на данные, security, публичный API или необратимое пользовательское поведение — разрешить её явно. Рядовые reversible implementation choices основной агент принимает сам.

**Хирургические изменения:** не смешивать unrelated refactoring с feature/fix.

**Дефект:** reproduction/contract → fix → regression.

**CI:** исправлять фактическую причину из логов, а не предполагаемую.

**Перед завершением:** сверить diff, CI и acceptance; непроверенное назвать явно.

## 6. Текущий продуктовый порядок

Уже реализованы:

- master scheduling;
- backup/restore;
- web cabinet;
- real catalog;
- client identity + booking requests;
- deterministic client bot;
- multi-master ADR-009 binding;
- client notifications/reachability;
- permanent client runtime lifecycle.

Текущий фокус:

1. mobile production acceptance/regressions;
2. schedule transparency/UX;
3. web render tech debt;
4. repository branch protection;
5. затем self-service SaaS onboarding мастеров (#223).

Billing/subscriptions и публичный SaaS management не являются частью уже реализованного ADR-009.

## 7. Чек-лист перед PR

- [ ] Проверено фактическое состояние `main`?
- [ ] Проверено, что механизм уже не существует?
- [ ] Решение соразмерно текущему масштабу?
- [ ] Security/owner/privacy invariants не ослаблены?
- [ ] Candidate действительно isolated, если он нужен?
- [ ] PR-head и merged SHA не смешиваются в отчётах?
- [ ] Production deploy идёт только штатным entrypoint?
- [ ] Все acceptance criteria либо проверены, либо явно оставлены открытыми?
