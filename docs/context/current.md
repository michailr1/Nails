# Nails — текущий контекст для продолжения работы

Дата фиксации: **17 июля 2026 года**.

Сначала прочитать [`../../AGENTS.md`](../../AGENTS.md), затем этот файл, [`../operations/engineering-principles.md`](../operations/engineering-principles.md), [`../operations/production-infrastructure.md`](../operations/production-infrastructure.md), [`../operations/hermes-plugin-runtime.md`](../operations/hermes-plugin-runtime.md) и [`../operations/backups.md`](../operations/backups.md).

Это handoff для нового контекста основного агента. Не угадывай состояние по памяти — проверяй по GitHub, а для production — по фактическому preflight.

## 1. Рабочий контракт

```text
repository: michailr1/Nails
production hostname: de.funti.cc
production repo: /opt/nails/repo
backend env: /opt/nails/.env
backend API: http://127.0.0.1:8210
health: /health
readiness: /ready
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

Production compose требует явный `--env-file /opt/nails/.env`. Host API port определяется через compose и сейчас равен `8210`. Корректный readiness endpoint — `/ready`, не `/readiness`.

## 3. Актуальный production milestone

Последний подтверждённый GitHub `main` и production checkout:

```text
main SHA: 847a6342911b5bf32a9e6c0885065e161c6d2d06
PR #106: merged fast-forward
issue #100: completed
ADR-006: accepted and deployed
working_tree_clean=true
nails-api=running
container_health=healthy
api_bind=127.0.0.1:8210
GET /health=200
GET /ready=200
gateway_active=true
```

Shutdown/restart Telegram-уведомления остаются отключены только для профиля Nails. Backup timer остаётся enabled/active.

Работает: onboarding; услуги; календарь и доступность; несколько интервалов в день; preview изменения доступности; клиентские карточки с расширенными private fields; exact/candidate поиск; переименование карточки; общий список активных клиенток; создание, корректный перенос и мягкая отмена записей; negative feedback; автоматические backup/restore tests.

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

## 5. Завершённый этап: NAILS-003

Issue #104 закрывается как реализованный фактическими механизмами `availability_intervals`, PR #105 и ADR-006/PR #106.

Поддерживается:

- несколько положительных интервалов подсказок на конкретную дату;
- частичное закрытие через замену одного окна несколькими итоговыми окнами;
- дополнительное открытие через тот же итоговый набор;
- read-only `preview_availability` до подтверждения;
- сводка «сейчас → будет»;
- единственный write `update_availability`;
- owner schedule lock, audit и идемпотентность;
- исправление повторной заменой;
- снятие настройки через `state=unknown`;
- целый выходной через `state=unavailable`;
- защита существующих записей при попытке поставить целый выходной.

ADR-006 определяет финальную семантику:

- явно названное время доступно по умолчанию;
- положительные интервалы и диапазон `10:00–23:00` формируют только подсказки;
- явная запись разрешена вне сетки и вне положительного окна;
- отказ только при целом выходном или overlap с active booking с учётом buffers;
- жёсткие частичные запреты не вводятся, потому что противоречат этой модели.

## 6. Следующий этап: web-интерфейс мастера

Порядок после пилота:

1. NAILS-003 — завершён;
2. web-интерфейс мастера — следующий;
3. клиентский контур ADR-004 — только после web.

ADR-005 уже подготовлен в отдельном открытом PR #87, но был создан до завершения NAILS-003. Перед merge необходимо:

- сверить ADR с актуальным `main` и ADR-006;
- убрать устаревшие допущения;
- убедиться, что web является тонким слоем над существующим Booking API;
- не выставлять loopback API напрямую наружу;
- сохранить owner scoping, confirmation, audit, CSRF и защищённые сессии;
- после принятия ADR создать отдельный минимальный implementation issue.

## 7. Известные грабли

1. Не добавлять одноразовые deploy/install scripts.
2. Не выполнять production restore поверх рабочей DB.
3. Не печатать `.env`, token, chat ID или dump content.
4. CI-lint чинить только после воспроизведения; Ruff imports — только автофиксом.
5. Candidate checkout остаётся на baseline; merge только exact validated head.
6. `app.routes` показывает mount entries как пустые paths; полные scheduling paths проверять через router или HTTP.
7. Не считать открытый issue доказательством незавершённого дефекта: сначала проверять фактический `main`, merged PR и regression tests.
8. Не возвращать shutdown/restart Telegram-уведомления профилю Nails при обновлении Hermes, unit-файла или profile runtime.
9. Compose-команды production выполнять с `--env-file /opt/nails/.env`.
10. Проверять readiness через `/ready`, а не `/readiness`.

## 8. Точка продолжения

```text
1. проверить CI документационного PR закрытия NAILS-003
2. fast-forward merge документации без production deploy
3. закрыть issue #104 как completed
4. ревью и актуализация ADR-005 / PR #87 относительно main и ADR-006
5. принять ADR-005
6. создать implementation issue минимального web-интерфейса мастера
```
