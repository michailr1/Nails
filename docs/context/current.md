# Nails — текущий контекст для продолжения работы

Дата фиксации: **14 июля 2026 года**.

Этот файл — первая точка входа для нового контекстного окна. Перед любыми действиями прочитать также [`../../AGENTS.md`](../../AGENTS.md), [`../operations/production-infrastructure.md`](../operations/production-infrastructure.md) и [`../operations/hermes-plugin-runtime.md`](../operations/hermes-plugin-runtime.md).

## 1. Рабочий контракт

```text
repository: michailr1/Nails
production hostname: de.funti.cc
production repo: /opt/nails/repo
backend env: /opt/nails/.env
backend API: http://127.0.0.1:8210
Hermes profile: /root/.hermes/profiles/nails
Hermes config: /root/.hermes/profiles/nails/config.yaml
branch: main
```

Ответственность:

- основной агент ChatGPT анализирует, пишет код, изменяет GitHub, проводит review/CI, выполняет merge и готовит точные runbooks;
- VPS-агент только исполняет заранее утверждённый runbook и не исправляет файлы самостоятельно;
- один живой Telegram-тест выполняется за раз;
- issue закрывается только после production deployment и ручной приёмки.

## 2. Фактическое production-состояние

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

GitHub `main` содержит последующий documentation-only commit:

```text
5c1d4d73f58851c5fb20c36dca7d591ff3f96583
```

Он ещё не требуется на production, потому что application runtime остаётся release `385a929…`.

## 3. Hermes production

```text
Hermes Agent v0.18.2 (2026.7.7.2)
Python 3.11.15
onboarding plugin: nails-onboarding 0.5.0
scheduling plugin: nails-scheduling 0.1.0
tools: nails_onboarding, nails_scheduling
```

Production configuration содержит оба plugin keys и оба Telegram toolsets.

Проверенные особенности Hermes:

- gateway управляется root user-level systemd;
- `_get_platform_tools()` возвращает set-like unordered collection;
- toolsets нужно сравнивать как множество, а не по порядку;
- verification использует `discover_plugins()`, а не `discover_plugins(force=True)`;
- V2 rollback был успешным: `ROLLBACK_PERFORMED=true`;
- V1 или V2 больше никогда не запускать.

## 4. Активная задача

```text
Issue #34 — NAILS-002E4: Restricted Hermes scheduling tool и Telegram happy path
PR #44 — fix: resolve calendar dates and edit availability directly
branch: fix/date-resolution-schedule-editing
```

Deployment scheduling plugin `0.1.0` завершился успешно, но ручная Telegram-приёмка обнаружила два blocking production-дефекта. Старый acceptance остановлен до исправления и нового deployment.

## 5. Обнаруженный дефект №1 — неверная дата и день недели

Пользователь сообщил график словами:

```text
вторник, среда и пятница
```

Агент сохранил:

```text
14 июля
15 июля
18 июля
```

Правильно:

```text
14 июля 2026 — вторник
15 июля 2026 — среда
17 июля 2026 — пятница
18 июля 2026 — суббота
```

Причина:

- backend `day_view` и `free_slots` уже вычисляют `weekday_iso` правильно;
- модель сама преобразовала слово «пятница» в дату до вызова backend;
- она продолжила последовательность чисел и не сверила реальный календарь.

Фраза агента «Ошибка в моей логике вычисления дат» не является достаточным исправлением. Модель больше не должна вычислять календарь вообще.

## 6. Решение дефекта даты

PR #44 добавляет backend-trusted resolver:

```text
POST /api/v1/scheduling/date/resolve
nails_scheduling action=resolve_date
```

Поддерживаются:

- полная дата с годом;
- день и месяц без года;
- сегодня/завтра/через N дней;
- ближайший день недели;
- день недели на текущей или следующей неделе;
- ближайший год для даты без года;
- leap-day и переход года.

Backend возвращает:

```text
timezone
today
today_weekday_iso
day
weekday_iso
is_past
```

Skills запрещают модели самостоятельно вычислять дату, год или день недели. Для дальнейших операций используются только `result.day` и `result.weekday_iso`.

Regression:

```text
backend-local today: 2026-07-13
weekday 5 nearest_future -> 2026-07-17, weekday_iso=5
18 July without year -> 2026-07-18, weekday_iso=6
```

## 7. Обнаруженный дефект №2 — нельзя исправить график

Production scheduling plugin `0.1.0` умеет читать расписание, искать окна и создавать клиенток/записи, но не умеет менять `availability_intervals`.

Агент предложил:

```text
Перезапустить настройку — пройти onboarding заново
```

Это неправильный пользовательский опыт. Завершённый onboarding — первичная настройка, а не единственный интерфейс управления календарём.

## 8. Решение дефекта графика

PR #44 обновляет scheduling plugin до candidate version `0.2.0` и добавляет:

```text
PUT /api/v1/scheduling/availability
nails_scheduling action=update_availability
```

Состояния конкретной даты:

```text
available   — подтверждённые рабочие интервалы
unavailable — подтверждённый выходной
unknown     — удалить ошибочно сохранённую дату, не объявляя её выходным
```

Безопасность:

- только явно названные даты заменяются;
- все остальные даты сохраняются;
- несколько дат меняются атомарно;
- повтор той же операции возвращает `changed=false`;
- перед write агент читает текущее состояние и показывает «сейчас → будет»;
- write требует явного подтверждения;
- активная запись защищена: если новый график её вытеснит, вся операция отклоняется;
- audit содержит только дату, state и число интервалов;
- onboarding state/drafts не открываются и не переписываются.

## 9. Правильное желаемое состояние данных

После deployment исправление должно быть выполнено через обычный Telegram flow, без SQL и без повторного onboarding:

```text
2026-07-14 11:00–20:00 — сохранить
2026-07-15 11:00–20:00 — сохранить
2026-07-17 11:00–15:00 — добавить
2026-07-18 — удалить как ошибочную дату, state=unknown
```

18 июля не нужно автоматически превращать в выходной: пользователь сообщил, что дата ошибочная, а не что он точно не работает.

## 10. Старый acceptance приостановлен

Предыдущая точка проверки была:

```text
Что у меня 18 июля?
```

Старое ожидание `18 июля 11:00–15:00` признано неверным. Не продолжать старую последовательность и не создавать на 18 июля клиенток или записи.

До нового deployment никакие дополнительные live Telegram writes не выполнять.

## 11. Состояние PR #44

Реализовано:

- deterministic backend date resolver;
- direct availability replacement;
- booking-conflict protection;
- owner-scoped trusted identity;
- scheduling schema/actions/presenters;
- scheduling and onboarding dialogue rules;
- backend regression tests;
- plugin tests для Python 3.11/3.12.

Первый CI обнаружил только:

- Ruff formatting scheduling plugin;
- хрупкие точные фразы onboarding regression test.

Они исправлены. Backend job первого прогона был полностью green. Повторный CI выполняется на head:

```text
87efb324e70d3fdfc2cbeea025584ba254c3f528
```

Не считать PR готовым до полного green CI и review threads check.

## 12. Deployment impact после merge

Новая версия меняет backend code и runtime Hermes files.

Потребуется отдельный reviewed runbook, который:

1. проверит production baseline `385a929…` и clean tree;
2. создаст database и runtime backups;
3. fast-forward production repo до exact merged SHA;
4. rebuild/recreate только `nails-api`;
5. не перезапустит и не заменит `nails-db` и Docker daemon;
6. не выполнит migration, Alembic останется `0006`;
7. установит scheduling plugin `0.2.0`;
8. установит обновлённые scheduling и onboarding skills;
9. перезапустит только root user-level Hermes gateway;
10. проверит plugin registry/Telegram visibility;
11. проверит health/readiness и rollback boundaries.

API container при таком deployment ожидаемо изменится. DB container и Docker daemon должны остаться прежними.

## 13. Новая production-приёмка после deployment

Строго по одному сообщению.

### Шаг 1 — resolver

```text
Какая дата у ближайшей пятницы?
```

Ожидать:

```text
17 июля 2026 года
пятница
```

Ответ должен опираться на `resolve_date`, а не рассуждение модели.

### Шаг 2 — запрос исправления

```text
Исправь график: 17 июля работаю с 11:00 до 15:00, а ошибочную дату 18 июля убери.
```

Ожидать:

- resolver для обеих дат;
- чтение текущего состояния 17 и 18 июля;
- сводку «сейчас → будет»;
- объяснение, что 18 июля станет неизвестной датой, а не свободной или выходным;
- вопрос подтверждения;
- write ещё не выполнен.

### Шаг 3 — подтверждение

После явного подтверждения ожидать `update_availability` и успешный результат.

### Шаг 4 — проверка

Проверить:

```text
17 июля: available 11:00–15:00
18 июля: availability_known=false
14 июля: без изменений
15 июля: без изменений
```

Только после этого продолжать free slots, client creation и booking acceptance.

## 14. Следующее действие

Текущая точка остановки:

```text
дождаться полного CI PR #44
исправить замечания
проверить review threads
merge
подготовить новый deployment runbook
```

Production пока не менять и не корректировать schedule вручную.
