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

Последний подтверждённый GitHub `main`:

```text
main SHA: 0c08ffcd06752e13b8fa1372058d1dce079c455e
PR #103: merged fast-forward
```

PR #103 зафиксировал отключение Hermes shutdown/restart Telegram-уведомлений только для профиля Nails. Production-проверка подтвердила:

```text
profile=nails
telegram_gateway_restart_notification=false
gateway_active=true
api_health=true
api_readiness=true
SHUTDOWN_NOTIFICATION_DISABLED=true
```

Также подтверждено:

```text
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

## 5. Активный этап: NAILS-003, issue #104

Порядок после пилота зафиксирован:

1. скорректировать ограничения рабочего времени;
2. сделать web-интерфейс мастера;
3. только затем двигать клиентский контур ADR-004.

Активный первый slice — draft PR #105 `NAILS-003: preview working-time restrictions before mutation`.

```text
base main: 0c08ffcd06752e13b8fa1372058d1dce079c455e
active branch: feat/nails-003-availability-preview
latest documented head before final CI: 660b0f2391294545e3d2972398e528906516a130
Alembic: unchanged
new tables: none
```

Фактическая модель рабочего времени — `availability_intervals`, а не отдельные `schedule_rules`/`schedule_exceptions`. Existing write `replace_availability` уже:

- заменяет итоговый набор интервалов конкретной даты;
- блокирует вытеснение scheduled bookings с учётом reserved interval и buffers;
- сериализуется owner schedule lock;
- пишет safe audit;
- идемпотентен по фактическому состоянию.

PR #105 добавляет read-only `preview_availability` поверх того же запроса и той же авторитетной логики. Preview показывает текущее и предлагаемое состояние, `changed`, `can_apply` и конкретные конфликтующие записи. `update_availability` остаётся единственным write-путём и повторно проверяет конфликт при мутации.

Skill-flow после PR #105:

```text
resolve_date → day_view → preview_availability →
сводка сейчас/будет → явное подтверждение →
update_availability → day_view readback
```

Если `can_apply=false`, write запрещён; существующие записи не переносятся и не отменяются автоматически.

PR #105 — отдельный инкремент issue #104, а не полная реализация issue #100 / ADR-006 и не переход к модели «открыто по умолчанию».

## 6. Известные грабли

1. Не добавлять одноразовые deploy/install scripts.
2. Не выполнять production restore поверх рабочей DB.
3. Не печатать `.env`, token, chat ID или dump content.
4. CI-lint чинить только после воспроизведения; Ruff imports — только автофиксом.
5. Candidate checkout остаётся на baseline; merge только exact validated head.
6. `app.routes` показывает mount entries как пустые paths; полные scheduling paths проверять через router или HTTP.
7. Не считать открытый issue доказательством незавершённого дефекта: сначала проверять фактический `main`, merged PR и regression tests.
8. Не возвращать shutdown/restart Telegram-уведомления профилю Nails при обновлении Hermes, unit-файла или profile runtime.
9. Отсутствующий `production-infrastructure-contract` допустим, если PR не меняет охраняемые path-filter файлы.

## 7. Точка продолжения

```text
1. дождаться зелёного CI на финальном head PR #105
2. проверить unresolved review threads и ff от свежего main
3. выполнить candidate validation exact PR-head SHA через постоянный deploy.sh
4. только после candidate fast-forward merge того же SHA
5. finalize production checkout и Telegram acceptance preview → confirmation → update → readback
6. после production закрыть первый slice #104 и проектировать следующий минимальный slice ограничений
```
