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
production SHA: 429130e5b8d4908e3a9d39bd61eb9448ac3dd386
PR #96: verified automated PostgreSQL backups
checkout = origin/main = running SHA
health = 200
readiness = 200
gateway = active
backup timer = enabled, active
```

Работает: онбординг; услуги; календарь и доступность; клиентские карточки с расширенными private fields; exact/candidate поиск; переименование карточки; общий список активных клиенток; создание, корректный перенос и мягкая отмена записей.

Корректный перенос уже реализован:

- PR #62 удалил ошибочную `free_slots`-предпроверку из plugin-flow;
- backend `reschedule` исключает текущую переносимую запись через `exclude_booking_id`;
- конфликты с другими записями, buffers и рабочим временем сохраняются;
- повторный перенос остаётся идемпотентным;
- regression tests присутствуют;
- PR #66 закрепил fresh-read/readback contract;
- PR #74 добавил verified readback в одном tool-вызове.

Issue #61 остаётся открытым только как контейнер отдельных UX-дефектов. Самоблокировка записи при переносе уже не является незавершённой задачей.

## 4. Завершённый этап: NAILS-002F

Issue #91 и PR #96 завершены.

Постоянный production-механизм:

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

Финальная production-приёмка подтверждена: ручной backup успешен, isolated restore совпал, временных restore DB нет, архив получен в Telegram, timer активен.

## 5. Известные грабли

1. Не добавлять одноразовые deploy/install scripts.
2. Не выполнять production restore поверх рабочей DB.
3. Не печатать `.env`, token, chat ID или dump content.
4. CI-lint чинить только после воспроизведения; Ruff imports — только автофиксом.
5. Candidate checkout остаётся на baseline; merge только exact validated head.
6. `app.routes` показывает mount entries как пустые paths; полные scheduling paths проверять через router или HTTP.
7. Не считать открытый issue доказательством незавершённого дефекта: сначала проверять фактический `main`, merged PR и regression tests.

## 6. Точка продолжения

```text
1. не планировать повторно исправление self-reschedule: оно уже в production
2. issue #61 рассматривать только по оставшимся UX-пунктам, а не по исходному дефекту переноса
3. перед выбором следующей задачи сверить открытые issues с фактическим кодом и merged PR
4. поддерживать current.md после каждого завершённого production milestone
```
