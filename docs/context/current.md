# Nails — текущий контекст для продолжения работы

Дата фиксации: **14 июля 2026 года**.

Сначала прочитать [`../../AGENTS.md`](../../AGENTS.md), затем этот файл, [`../operations/production-infrastructure.md`](../operations/production-infrastructure.md) и [`../operations/hermes-plugin-runtime.md`](../operations/hermes-plugin-runtime.md).

## 1. Рабочий контракт

```text
repository: michailr1/Nails
production hostname: de.funti.cc
production repo: /opt/nails/repo
backend env: /opt/nails/.env
backend API: http://127.0.0.1:8210
Hermes profile: /root/.hermes/profiles/nails
Hermes config: /root/.hermes/profiles/nails/config.yaml
production branch: main
```

- основной агент ChatGPT пишет код, меняет GitHub, проводит review/CI, выполняет merge и готовит точные runbooks;
- VPS-агент только исполняет утверждённый merged runbook;
- один живой Telegram-тест выполняется за раз;
- Issue #34 закрывается только после deployment и ручной приёмки.

## 2. Доказанное production-состояние

Последний полученный production-отчёт:

```text
production HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3
working tree: clean
Alembic: 0006
backend health: ok
backend ready: ok
gateway: active
nails-onboarding: 0.5.0
nails-scheduling: 0.1.0
```

Последний доказанный успешный deployment:

```text
runbook: ops/deploy/nails-002e4-v3.sh
success marker: NAILS_002E4_V3_DEPLOYMENT_OK
```

GitHub `main` содержит PR #44 и PR #45, но пользователь ещё не прислал результат E5. Поэтому нельзя утверждать, что production уже находится на `a0ef8c5c26301a9f6950544afd0e070b7e691582` или plugin `0.2.0`.

## 3. E5 — date resolver и изменение графика

Код PR #44 merged:

```text
merge SHA: c9e400c80398bd4367aad0ed0416ee0fc6a79b2d
```

Добавлено:

```text
POST /api/v1/scheduling/date/resolve
action=resolve_date
PUT /api/v1/scheduling/availability
action=update_availability
```

Модель не вычисляет дату, год или weekday самостоятельно. График меняется по названным датам без повторного onboarding.

Deployment runbook PR #45 merged:

```text
branch: ops/nails-002e5-date-availability
release SHA: a0ef8c5c26301a9f6950544afd0e070b7e691582
runbook: ops/deploy/nails-002e5-date-availability.sh
success marker: NAILS_002E5_DEPLOYMENT_OK
calendar_data_changed_by_deployment=false
manual_sql_executed=false
```

E5 запрещено считать выполненным, пока не получен полный VPS-вывод с маркером `NAILS_002E5_DEPLOYMENT_OK` или блоком rollback.

## 4. Найденные UX-дефекты

### 4.1 Неверное разрешение даты

Агент сохранил пятницу как 18 июля 2026 года. Правильно:

```text
14 июля 2026 — вторник
15 июля 2026 — среда
17 июля 2026 — пятница
18 июля 2026 — суббота
```

### 4.2 График нельзя было менять после onboarding

Scheduling plugin `0.1.0` не имел availability write-action и предлагал пройти completed onboarding заново. Это исправлено PR #44, но production deployment ещё не подтверждён.

### 4.3 Услуги нельзя было менять после onboarding

Агент сообщил, что изменение цены, длительности, buffers или названия требует перезапуска настройки. Это третий дефект той же архитектурной природы.

Правильный продуктовый принцип:

> Onboarding — только удобный мастер первичного заполнения. После `complete` рабочие услуги, график, клиентки и записи управляются доменными restricted operations. Повторный onboarding не является способом обычного редактирования.

## 5. Активный PR #46 — service management

```text
PR: #46
branch: feat/service-management
candidate scheduling plugin: 0.3.0
production deployed: false
Alembic change: none
```

Новые actions:

```text
find_service
create_service
update_service
```

Поддерживается:

- список активных услуг;
- список активных и архивных услуг;
- exact lookup, включая архив;
- создание новой услуги после onboarding;
- изменение публичного названия и описания;
- изменение цены и валюты;
- изменение длительности;
- изменение buffer до и после;
- безопасная архивация;
- восстановление архивной услуги.

Правила безопасности и истории:

- Telegram identity только из trusted context;
- fixed loopback endpoints;
- перед write показывается «сейчас → будет»;
- write требует `confirmed=true`;
- одинаковое повторное создание возвращает `created=false`;
- одинаковое повторное изменение возвращает `changed=false`;
- конфликт имени возвращает `service_name_conflict`;
- физического удаления услуги нет;
- «удали услугу» означает `is_active=false`;
- архивная услуга недоступна для новых записей;
- существующие записи не отменяются и не пересчитываются;
- существующие записи сохраняют snapshots цены, валюты, длительности и buffers;
- новые значения используются только для будущих записей;
- переименование меняет актуальное связанное название услуги;
- audit не содержит персонального текста.

## 6. Текущее состояние PR #46

Реализованы backend endpoints, scheduling plugin `0.3.0`, оба skills и regression tests.

Lint исправлен. Scheduling plugin tests проходят на Python 3.11 в focused-прогоне; временные diagnostic/autofix workflows удалены из ветки. Финальный обычный CI после удаления временных файлов ещё должен стать полностью зелёным.

PR #46 нельзя merge до двух условий:

1. полный green CI и отсутствие review threads;
2. получен фактический результат E5 production deployment.

Причина второго условия: E5 runbook проверяет, что `origin/main` равен exact release SHA `a0ef8c5…`. Если раньше времени продвинуть `main`, утверждённый E5 runbook перестанет проходить preflight.

## 7. Старый acceptance отменён

Запрос:

```text
Что у меня 18 июля?
```

и ожидание рабочего интервала на 18 июля основаны на ошибочных данных. Старую последовательность не продолжать.

Правильное желаемое состояние после подтверждённого Telegram-flow:

```text
2026-07-14 11:00–20:00 — сохранить
2026-07-15 11:00–20:00 — сохранить
2026-07-17 11:00–15:00 — добавить
2026-07-18 — state=unknown
```

## 8. Следующая production-приёмка после E5

Строго по одному сообщению:

1. `Какая дата у ближайшей пятницы?` → 17 июля 2026, пятница.
2. `Исправь график: 17 июля работаю с 11:00 до 15:00, а ошибочную дату 18 июля убери.`
3. Проверить «сейчас → будет» и отсутствие write до подтверждения.
4. Подтвердить и проверить 17/18 июля, а также неизменность 14/15 июля.

Управление услугами тестировать только после отдельного deployment service-management release.

## 9. Запрещённые действия

- не считать E5 успешным без VPS-отчёта;
- не merge PR #46 до результата E5;
- не исправлять календарь или услуги SQL-командами;
- не проходить onboarding заново ради графика или услуг;
- не запускать V1 или V2;
- не давать VPS-агенту самостоятельные команды вне merged runbook.

## 10. Точка продолжения

```text
дождаться полного CI PR #46
исправить оставшиеся tests при необходимости
проверить review threads
получить от пользователя E5 VPS output
проверить deployment/rollback
только затем merge PR #46 и готовить отдельный service-management runbook
```
