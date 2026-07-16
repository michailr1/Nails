# Nails — текущий контекст для продолжения работы

Дата фиксации: **16 июля 2026 года**.

Сначала прочитать [`../../AGENTS.md`](../../AGENTS.md), затем этот файл, [`../operations/engineering-principles.md`](../operations/engineering-principles.md), [`../operations/production-infrastructure.md`](../operations/production-infrastructure.md), [`../operations/hermes-plugin-runtime.md`](../operations/hermes-plugin-runtime.md) и [`../operations/backups.md`](../operations/backups.md).

Это handoff для нового контекста основного агента. Не угадывай состояние по памяти — проверяй по GitHub, а для production — по фактическому preflight.

## 1. Рабочий контракт

```text
repository: michailr1/Nails
production hostname: de.funti.cc
production repo: /opt/nails/repo
backend env: /opt/nails/.env
backend API: http://127.0.0.1:8210
Hermes profile: /root/.hermes/profiles/nails
production branch: main
Hermes plugins: nails-onboarding, nails-scheduling
```

- основной агент пишет код, меняет GitHub, проводит review/CI, мержит и готовит точные runbooks;
- VPS-агент только исполняет утверждённый runbook и возвращает компактный отчёт;
- один живой Telegram-тест за раз;
- в GitHub — только роли (`master`, `admin`, `client`), без персональных имён; имя ассистента мастера — «Нэйли».

## 2. Деплой — один постоянный скрипт

Все релизы идут через `ops/deploy/deploy.sh <exact-SHA>`. Поток: PR → CI → candidate exact PR-head SHA → fast-forward того же SHA → finalize `git merge --ff-only`. Rollback = deploy предыдущего SHA. **Production state не предполагать**: каждый запуск устанавливает его свежим preflight.

## 3. Актуальный production milestone

```text
production SHA: f53a77a213cfb21cf63839d5e3c10d7e01bcd298
PR #95: owner-scoped list_clients
checkout = origin/main = running SHA
health = 200
readiness = 200
gateway = active
```

Работает: онбординг; услуги; календарь и доступность; клиентские карточки с расширенными private fields; exact/candidate поиск; переименование карточки; общий список активных клиенток; создание, перенос и мягкая отмена записей.

## 4. Активная работа: NAILS-002F

Основная задача: issue #91 `automated PostgreSQL backup, restore verification and retention`.

Дубли #89 и #8 закрыты как duplicate. Рабочая ветка:

```text
feat/automated-backup-restore
```

Реализуемый постоянный механизм:

- daily `pg_dump` + `gzip -t`;
- restore в отдельную временную DB;
- совпадение Alembic revision и row counts всех public tables;
- гарантированное удаление временной DB;
- daily/weekly/monthly/pre-deploy/runtime/log retention;
- `hermes-local-patches` не удаляется;
- Telegram archive администратору до 15 MiB;
- disk warning 80%, critical 90%;
- root system `nails-backup.service` + `nails-backup.timer`;
- установка только через постоянный `deploy.sh`;
- источник истины: `docs/operations/backups.md`.

## 5. Известные грабли

1. Не добавлять одноразовые deploy/install scripts.
2. Не выполнять production restore поверх рабочей DB.
3. Не печатать `.env`, token, chat ID или dump content.
4. CI-lint чинить только после воспроизведения; Ruff imports — только автофиксом.
5. Candidate checkout остаётся на baseline; merge только exact validated head.
6. `app.routes` показывает mount entries как пустые paths; полные scheduling paths проверять через router или HTTP.

## 6. Точка продолжения

```text
1. завершить PR NAILS-002F: review diff, CI, contract/retention tests
2. candidate устанавливает timer, но ручной backup запускается отдельной проверкой
3. production manual run: dump + gzip + isolated restore + counts + Telegram receipt
4. retention dry-run, затем apply; проверить сохранность hermes-local-patches
5. ff-merge exact candidate SHA, finalize checkout, закрыть #91
6. следующий функциональный defect: issue #61 reschedule slot excluding current booking
```
