# Nails — текущий контекст для продолжения работы

Дата фиксации: **14 июля 2026 года**.

Этот файл — первая точка входа для нового контекстного окна. Перед работой прочитать [`../../AGENTS.md`](../../AGENTS.md), затем этот файл, [`../operations/production-infrastructure.md`](../operations/production-infrastructure.md) и [`../operations/hermes-plugin-runtime.md`](../operations/hermes-plugin-runtime.md).

## 1. Контракт работы

```text
repository: michailr1/Nails
production hostname: de.funti.cc
production repo: /opt/nails/repo
backend env: /opt/nails/.env
backend API: http://127.0.0.1:8210
Hermes profile: /root/.hermes/profiles/nails
Hermes config: /root/.hermes/profiles/nails/config.yaml
working branch in production: main
```

- основной агент ChatGPT пишет код, меняет GitHub, проводит review/CI, выполняет merge и готовит точные runbooks;
- VPS-агент только исполняет merged runbook без самостоятельных исправлений;
- один живой Telegram-тест выполняется за раз;
- Issue #34 закрывается только после deployment и полной ручной приёмки.

## 2. Текущее production-состояние

```text
production HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3
working tree after last deployment: clean
Alembic: 0006
backend health: ok
backend ready: ok
gateway: active
```

Последний успешный deployment:

```text
runbook: ops/deploy/nails-002e4-v3.sh
success marker: NAILS_002E4_V3_DEPLOYMENT_OK
backup: /root/.hermes/profiles/nails/backups/nails-002e4-v3-20260713T215800Z
```

Production plugins:

```text
nails-onboarding 0.5.0
nails-scheduling 0.1.0
tools: nails_onboarding, nails_scheduling
```

GitHub `main` уже содержит исправление кода:

```text
PR #44
merge SHA: c9e400c80398bd4367aad0ed0416ee0fc6a79b2d
```

Но production ещё не обновлён до этого кода.

## 3. Проверенные особенности Hermes

```text
Hermes Agent v0.18.2 (2026.7.7.2)
Python 3.11.15
```

- gateway управляется root user-level systemd;
- `_get_platform_tools()` возвращает set-like unordered collection;
- toolsets сравниваются как множество, не по порядку;
- verification использует `discover_plugins()`, а не `discover_plugins(force=True)`;
- V2 rollback доказан маркером `ROLLBACK_PERFORMED=true`;
- V1 или V2 никогда не запускать повторно.

## 4. Найденные production-дефекты

### 4.1 Неверная дата и день недели

Пользователь назвал вторник, среду и пятницу. Агент сохранил 14, 15 и 18 июля 2026 года. Правильно:

```text
14 июля 2026 — вторник
15 июля 2026 — среда
17 июля 2026 — пятница
18 июля 2026 — суббота
```

Причина: модель сама преобразовала слово «пятница» в дату до backend-вызова и продолжила последовательность чисел. Backend `day_view` вычислял `weekday_iso` правильно, но получил уже ошибочную дату.

Фраза «Ошибка в моей логике вычисления дат» не является исправлением. Модель не должна вычислять календарь самостоятельно.

### 4.2 Нельзя исправить график после onboarding

Scheduling plugin `0.1.0` умеет читать график, искать окна и создавать клиенток/записи, но не умеет менять availability. Агент предложил пройти completed onboarding заново. Это признано неприемлемым пользовательским опытом.

## 5. Смёрженное исправление PR #44

Backend-trusted resolver:

```text
POST /api/v1/scheduling/date/resolve
nails_scheduling action=resolve_date
```

Поддерживаются:

- полная дата с годом;
- день и месяц без года;
- сегодня/завтра/через N дней;
- ближайший weekday;
- weekday текущей или следующей недели;
- переход года и leap-day.

Backend возвращает абсолютную дату и `weekday_iso`. Skills запрещают модели вычислять дату, год или день недели самостоятельно.

Direct availability management:

```text
PUT /api/v1/scheduling/availability
nails_scheduling action=update_availability
```

Состояния даты:

```text
available   — рабочие интервалы
unavailable — подтверждённый выходной
unknown     — удалить ошибочно сохранённую дату
```

Операция:

- меняет только явно названные даты;
- сохраняет все остальные даты;
- атомарна;
- повтор безопасен и возвращает `changed=false`;
- требует сводку «сейчас → будет» и явное подтверждение;
- запрещает изменение, которое вытеснит active booking;
- не открывает и не переписывает completed onboarding;
- пишет только безопасные audit metadata.

Candidate scheduling plugin:

```text
0.2.0
```

PR #44 полностью зелёный:

```text
Agent responsibility contract #25
Production infrastructure contract #14
CI #115
backend
onboarding plugin Python 3.11/3.12
scheduling plugin Python 3.11/3.12
compose-smoke
review threads: none
```

## 6. Правильное желаемое состояние календаря

После deployment исправление выполняется через обычный Telegram-flow, без SQL и без повторного onboarding:

```text
2026-07-14 11:00–20:00 — сохранить
2026-07-15 11:00–20:00 — сохранить
2026-07-17 11:00–15:00 — добавить
2026-07-18 — удалить как ошибочную дату, state=unknown
```

`unknown` не означает выходной и не означает свободный день.

## 7. Старый acceptance отменён

Предыдущий запрос:

```text
Что у меня 18 июля?
```

и ожидание `18 июля 11:00–15:00` основаны на ошибочных данных. Старую последовательность не продолжать. До нового deployment не выполнять live Telegram writes.

## 8. Активный deployment candidate

```text
branch: ops/nails-002e5-date-availability
runbook: ops/deploy/nails-002e5-date-availability.sh
success marker: NAILS_002E5_DEPLOYMENT_OK
```

Runbook состоит из:

```text
ops/deploy/nails-002e5-date-availability.sh
ops/deploy/lib/nails-002e5-common.sh
ops/deploy/lib/nails-002e5-runtime.sh
```

Он должен:

1. проверить production baseline `385a929…` и exact approved release SHA;
2. доказать отсутствие Alembic changes и состояние `0006`;
3. создать PostgreSQL backup и runtime backup;
4. построить новый API image, пока старый API ещё работает;
5. остановить только root user-level Nails gateway;
6. пересоздать только `nails-api`;
7. сохранить `nails-db` и Docker daemon без изменений;
8. установить scheduling plugin `0.2.0` и оба skills;
9. не менять Hermes config;
10. проверить новые OpenAPI routes, plugin registry и Telegram actions;
11. запустить gateway и проверить журнал;
12. выполнить rollback repo/API image/runtime/gateway при ошибке.

Deployment не исправляет календарь и не вызывает scheduling tool:

```text
calendar_data_changed_by_deployment=false
manual_sql_executed=false
```

API container ожидаемо изменится. DB container и Docker daemon должны остаться прежними. Alembic останется `0006`; при старте API команда контейнера может выполнить безопасный `alembic upgrade head`, но schema revision не меняется.

## 9. Следующая production-приёмка после успешного E5

Строго по одному сообщению.

### Шаг 1 — resolver

```text
Какая дата у ближайшей пятницы?
```

Ожидать один breadcrumb `Думаю… (nails_scheduling)` и точный ответ:

```text
17 июля 2026 года
пятница
```

### Шаг 2 — запрос исправления

```text
Исправь график: 17 июля работаю с 11:00 до 15:00, а ошибочную дату 18 июля убери.
```

Ожидать:

- resolve обеих дат;
- чтение current state 17 и 18 июля;
- сводку «сейчас → будет»;
- объяснение, что 18 июля станет неизвестной датой, а не выходным/свободным днём;
- вопрос подтверждения;
- write ещё не выполнен.

### Шаг 3 — подтверждение и проверка

После явного подтверждения ожидать `update_availability`. Затем проверить:

```text
17 июля: available 11:00–15:00
18 июля: availability_known=false
14 июля: без изменений
15 июля: без изменений
```

Только после этого продолжать free slots, client creation и booking acceptance.

## 10. Точка продолжения

```text
добавить/проверить документацию E5 runbook
открыть ops PR
получить green CI и review
merge
выдать VPS-агенту exact release SHA и одну команду
после успешного deployment начать resolver acceptance
```
