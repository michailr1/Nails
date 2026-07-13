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

Пользователь не прислал результат E5, поэтому production также может находиться на строго проверяемом состоянии:

```text
HEAD: a0ef8c5c26301a9f6950544afd0e070b7e691582
nails-scheduling: 0.2.0
```

Никакое из этих состояний нельзя предполагать: E6 определяет его по фактическому HEAD и plugin list.

Проверенные особенности Hermes:

- gateway управляется root user-level systemd;
- `_get_platform_tools()` возвращает set-like unordered collection;
- toolsets сравниваются по множеству, а не по iteration order;
- verification использует `discover_plugins()`, а `discover_plugins(force=True)` запрещён;
- V2 rollback доказан маркером `ROLLBACK_PERFORMED=true`;
- V1 или V2 никогда не запускать повторно.

## 3. Смёрженные исправления

PR #44 merged как `c9e400c80398bd4367aad0ed0416ee0fc6a79b2d`:

```text
resolve_date
update_availability
```

PR #46 merged как `e4443a736c5a0d5a34239a5257b7764592834e5b`:

```text
find_service
create_service
update_service
```

Общий продуктовый принцип:

> Onboarding — только мастер первичного заполнения. После `complete` услуги, график, клиентки и записи управляются restricted domain operations. Повторный onboarding не используется для обычного редактирования.

Service management поддерживает создание, переименование, описание, цену, валюту, длительность, buffers, архив и восстановление. Существующие bookings сохраняют snapshots цены, валюты, длительности и buffers; новые значения применяются только к будущим bookings.

PR #46 final checks:

```text
CI #145: success
Agent responsibility contract #55: success
Production infrastructure contract #29: success
backend: success
onboarding plugin Python 3.11/3.12: success
scheduling plugin Python 3.11/3.12: success
compose-smoke: success
review threads: none
```

## 4. Активный deployment candidate

```text
branch: ops/nails-002e6-combined-operations
entrypoint: ops/deploy/nails-002e6-combined-operations.sh
runtime: ops/deploy/lib/nails-002e6-runtime.sh
shared rollback library: ops/deploy/lib/nails-002e5-common.sh
success marker: NAILS_002E6_DEPLOYMENT_OK
final scheduling plugin: 0.3.0
Alembic: 0006
```

E6 принимает только два исходных состояния:

```text
385a92962e3736553335d717adcdf4b83ac8a8b3 + scheduling 0.1.0
a0ef8c5c26301a9f6950544afd0e070b7e691582 + scheduling 0.2.0
```

Runbook:

- создаёт PostgreSQL и runtime backups;
- обновляет только `nails-api`, scheduling plugin и оба skills;
- не меняет `nails-db`, Docker daemon, Alembic revision или Hermes config;
- проверяет date, availability и service-management OpenAPI routes;
- проверяет plugin registry, Telegram visibility и полный action set;
- выполняет rollback к фактически обнаруженному исходному HEAD/plugin/image/runtime при ошибке;
- не изменяет календарь или услуги во время deployment.

Expected markers:

```text
calendar_data_changed_by_deployment=false
service_data_changed_by_deployment=false
manual_sql_executed=false
schema_revision_changed=false
```

## 5. Исторический E5

```text
ops/nails-002e5-date-availability
ops/deploy/nails-002e5-date-availability.sh
NAILS_002E5_DEPLOYMENT_OK
calendar_data_changed_by_deployment=false
manual_sql_executed=false
```

Отдельный E5 больше не выдаётся VPS-агенту: E6 безопасно поддерживает и pre-E5, и post-E5 baseline.

## 6. Acceptance после E6

По одному сообщению:

1. `Какая дата у ближайшей пятницы?` → 17 июля 2026, пятница.
2. Исправить график: 17 июля 11:00–15:00, ошибочную дату 18 июля убрать как `unknown`.
3. Проверить, что 14 и 15 июля не изменились.
4. Изменить цену одной услуги: exact lookup, «сейчас → будет», подтверждение.
5. Проверить новую цену для будущих записей и старый snapshot существующей записи.
6. Проверить архив и восстановление услуги без удаления истории.
7. Выполнить финальные read-only counts и log-privacy проверки.

Старый тест `Что у меня 18 июля?` с ожиданием рабочего интервала отменён.

## 7. Запрещённые действия

- не запускать отдельный E5;
- не считать production обновлённым без `NAILS_002E6_DEPLOYMENT_OK`;
- не исправлять календарь или услуги SQL-командами;
- не проходить onboarding заново ради графика или услуг;
- не запускать V1 или V2;
- не давать VPS-агенту самостоятельные команды.

## 8. Точка продолжения

```text
открыть E6 PR
получить green CI и review
merge E6 runbook
выдать VPS-агенту одну exact-SHA команду
проверить deployment output
после deployment выполнить acceptance по одному сообщению
```
