# Фактическое состояние проекта

Дата актуализации: **14 июля 2026 года**.

Для продолжения сначала читать [`context/current.md`](context/current.md).

## 1. Сводка

| Область | Состояние |
|---|---|
| Production repository | последний доказанный `HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3`, clean; допустим также фактический post-E5 HEAD `a0ef8c5c26301a9f6950544afd0e070b7e691582` |
| Backend API/PostgreSQL | healthy/ready по последнему production-отчёту |
| Alembic | `0006` |
| Hermes gateway | active по последнему production-отчёту |
| Onboarding plugin | production `0.5.0` |
| Scheduling plugin | допустимый baseline `0.1.0` или `0.2.0`; итоговый candidate `0.3.0` |
| Date/availability fix | PR #44 merged, `c9e400c80398bd4367aad0ed0416ee0fc6a79b2d` |
| NAILS-002E5 | PR #45 merged, отдельный запуск заменён E6 |
| Service management | PR #46 merged, `e4443a736c5a0d5a34239a5257b7764592834e5b` |
| Active deployment | NAILS-002E6 candidate |
| Last proven deployment | `NAILS_002E4_V3_DEPLOYMENT_OK` |
| Active issue | Issue #34 |

## 2. Продуктовый принцип

Onboarding — только мастер первичного заполнения. После завершения услуги, график, клиентки и записи редактируются через restricted domain operations.

Реализовано:

```text
resolve_date
update_availability
find_service
create_service
update_service
```

Service management поддерживает создание, переименование, описание, цену, валюту, длительность, buffers, архив и восстановление. Существующие bookings сохраняют snapshots; новые параметры применяются только к будущим bookings.

## 3. Проверки service-management кода

```text
PR #46 merged
CI #145 — success
Agent responsibility contract #55 — success
Production infrastructure contract #29 — success
backend — success
onboarding plugin Python 3.11/3.12 — success
scheduling plugin Python 3.11/3.12 — success
compose-smoke — success
review threads — none
```

## 4. NAILS-002E6

```text
branch: ops/nails-002e6-combined-operations
entrypoint: ops/deploy/nails-002e6-combined-operations.sh
success marker: NAILS_002E6_DEPLOYMENT_OK
final scheduling plugin: 0.3.0
```

Допустимые исходные состояния:

```text
HEAD 385a92962e3736553335d717adcdf4b83ac8a8b3 + scheduling 0.1.0
HEAD a0ef8c5c26301a9f6950544afd0e070b7e691582 + scheduling 0.2.0
```

Итог:

```text
точный date resolver
редактирование availability
service management
scheduling 0.3.0
Alembic 0006
nails-db unchanged
Docker daemon unchanged
```

Runbook создаёт database/runtime backups, обновляет только `nails-api`, plugin и skills, проверяет OpenAPI/actions, сохраняет Hermes config и выполняет rollback к обнаруженному baseline при ошибке.

Deployment не меняет calendar/service data и не выполняет ручной SQL.

## 5. Исторический E5

```text
NAILS-002E5
candidate `0.2.0`
NAILS_002E5_DEPLOYMENT_OK
```

Отдельный E5 больше не используется, потому что E6 безопасно принимает оба возможных baseline.

## 6. Acceptance

После E6:

1. Проверить ближайшую пятницу: 17 июля 2026.
2. Исправить 17/18 июля через подтверждаемую сводку.
3. Проверить неизменность 14/15 июля.
4. Изменить цену услуги без onboarding.
5. Проверить применение новой цены только к будущим bookings.
6. Проверить archive/reactivate без удаления истории.
7. Выполнить финальную read-only проверку counts и log privacy.
8. Закрыть Issue #34 после всех критериев.

Старый тест `Что у меня 18 июля?` с ожиданием рабочего интервала отменён.
