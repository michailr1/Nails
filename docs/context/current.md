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

## 2. Последнее доказанное production-состояние

```text
production HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3
working tree: clean
Alembic: 0006
backend health: ok
backend ready: ok
gateway: active
nails-onboarding: 0.5.0
nails-scheduling: 0.1.0
last success: NAILS_002E4_V3_DEPLOYMENT_OK
```

Проверенные особенности Hermes:

- gateway управляется root user-level systemd;
- `_get_platform_tools()` возвращает set-like unordered collection;
- toolsets сравниваются по множеству, а не по iteration order;
- verification использует `discover_plugins()`, а `discover_plugins(force=True)` запрещён;
- V2 rollback доказан маркером `ROLLBACK_PERFORMED=true`;
- V1 или V2 никогда не запускать повторно.

Пользователь не прислал результат E5. Поэтому нельзя утверждать, что production уже находится на `a0ef8c5c26301a9f6950544afd0e070b7e691582` или scheduling `0.2.0`.

## 3. Реализованные исправления

PR #44 merged как `c9e400c80398bd4367aad0ed0416ee0fc6a79b2d`:

```text
resolve_date
update_availability
```

Модель не вычисляет дату, год или weekday самостоятельно. График меняется по конкретным датам без повторного onboarding.

PR #46 добавляет scheduling `0.3.0`:

```text
find_service
create_service
update_service
```

Поддерживаются создание, переименование, описание, цена, валюта, длительность, buffers, архив и восстановление услуги.

Общий продуктовый принцип:

> Onboarding — только мастер первичного заполнения. После `complete` услуги, график, клиентки и записи управляются restricted domain operations. Повторный onboarding не используется для обычного редактирования.

## 4. Безопасность service management

- trusted Telegram owner identity;
- fixed loopback endpoints;
- exact lookup перед изменением;
- сводка «сейчас → будет»;
- write только при `confirmed=true`;
- repeat-safe create/update;
- `service_name_conflict` при занятом имени;
- физического удаления нет: «удали услугу» означает `is_active=false`;
- архив запрещает новые записи, но сохраняет историю;
- существующие bookings сохраняют snapshots цены, валюты, длительности и buffers;
- новые значения применяются только к будущим bookings;
- Alembic остаётся `0006`.

## 5. Проверки PR #46

```text
head: 81740eb4fedd94a8ccef602837c581bce3105f82
Agent responsibility contract #52: success
Production infrastructure contract #26: success
CI #142: success
backend: success
onboarding plugin Python 3.11/3.12: success
scheduling plugin Python 3.11/3.12: success
compose-smoke: success
review threads: none
```

Temporary diagnostic workflows удалены. PR #46 готов к merge.

## 6. Единая deployment-стратегия

Ранее merged E5:

```text
ops/nails-002e5-date-availability
ops/deploy/nails-002e5-date-availability.sh
NAILS_002E5_DEPLOYMENT_OK
calendar_data_changed_by_deployment=false
manual_sql_executed=false
```

Отдельный E5 больше не выдаётся VPS-агенту. После merge PR #46 создаётся новый объединённый runbook, который проверит и примет только один из двух исходных состояний:

```text
385a92962e3736553335d717adcdf4b83ac8a8b3 + scheduling 0.1.0
a0ef8c5c26301a9f6950544afd0e070b7e691582 + scheduling 0.2.0
```

В обоих случаях итогом будет backend с точными датами, редактированием графика и service management, scheduling `0.3.0`, Alembic `0006`, неизменные `nails-db` и Docker daemon.

Runbook обязан создать database/runtime backups, обновить только `nails-api`, plugin и skills, проверить OpenAPI/actions и выполнить rollback к фактически обнаруженному исходному состоянию при ошибке. Deployment не меняет календарь и услуги.

## 7. Acceptance после объединённого deployment

По одному сообщению:

1. `Какая дата у ближайшей пятницы?` → 17 июля 2026, пятница.
2. Исправить график: 17 июля 11:00–15:00, ошибочную дату 18 июля убрать как `unknown`.
3. Проверить, что 14 и 15 июля не изменились.
4. Изменить цену одной услуги: exact lookup, «сейчас → будет», подтверждение.
5. Проверить новую цену для будущих записей и старый snapshot существующей записи.
6. Проверить архив и восстановление услуги без удаления истории.

Старый тест `Что у меня 18 июля?` с ожиданием рабочего интервала отменён.

## 8. Запрещённые действия

- не запускать отдельный E5;
- не считать production обновлённым без нового runbook output;
- не исправлять календарь или услуги SQL-командами;
- не проходить onboarding заново ради графика или услуг;
- не запускать V1 или V2;
- не давать VPS-агенту самостоятельные команды.

## 9. Точка продолжения

```text
merge PR #46
зафиксировать merge SHA
подготовить combined deployment runbook
провести review/CI
merge runbook
выдать VPS-агенту одну exact-SHA команду
после deployment выполнить acceptance по одному сообщению
```
