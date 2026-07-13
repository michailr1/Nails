# Фактическое состояние проекта

Дата актуализации: **14 июля 2026 года**.

Для продолжения сначала читать [`context/current.md`](context/current.md).

## 1. Сводка

| Область | Состояние |
|---|---|
| Production repository | последний доказанный `HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3`, clean |
| Backend API/PostgreSQL | healthy/ready по последнему production-отчёту |
| Alembic | `0006` |
| Hermes gateway | active по последнему production-отчёту |
| Onboarding plugin | production `0.5.0` |
| Scheduling plugin | доказанный production `0.1.0`; E5 candidate `0.2.0`; итоговый candidate `0.3.0` |
| Date/availability fix | PR #44 merged, `c9e400c80398bd4367aad0ed0416ee0fc6a79b2d` |
| NAILS-002E5 | PR #45 merged, но отдельный запуск больше не используется |
| Service management | PR #46 green, готов к merge, ещё не deployed |
| Last proven deployment | `NAILS_002E4_V3_DEPLOYMENT_OK` |
| Active issue | Issue #34 |

## 2. Найденные UX-дефекты

1. Модель сопоставила пятницу с 18 июля 2026 года вместо 17 июля.
2. Изменение графика требовало повторного onboarding.
3. Изменение услуг, цены, длительности и buffers также требовало повторного onboarding.

Общий продуктовый принцип:

> Onboarding — только мастер первичного заполнения. После завершения рабочие данные редактируются через restricted domain operations.

## 3. Реализованный operational scope

PR #44:

```text
resolve_date
update_availability
```

PR #46, scheduling `0.3.0`:

```text
find_service
create_service
update_service
```

Service management поддерживает создание, переименование, описание, цену, валюту, длительность, оба buffers, архив и восстановление.

Безопасность:

- exact owner-scoped lookup;
- «сейчас → будет» и явное подтверждение;
- repeat-safe create/update;
- name-conflict protection;
- физического удаления нет;
- существующие bookings сохраняют price/currency/duration/buffer snapshots;
- новые параметры применяются только к будущим bookings;
- архив блокирует новые записи, но сохраняет историю;
- migration отсутствует, Alembic остаётся `0006`.

## 4. Проверки PR #46

```text
head: 81740eb4fedd94a8ccef602837c581bce3105f82
Agent responsibility contract #52 — success
Production infrastructure contract #26 — success
CI #142 — success
backend — success
onboarding plugin Python 3.11/3.12 — success
scheduling plugin Python 3.11/3.12 — success
compose-smoke — success
review threads — none
```

## 5. Единый deployment

Отдельный E5 не запускается. После merge PR #46 создаётся новый combined runbook, который принимает только один из двух проверяемых исходных вариантов:

```text
HEAD 385a92962e3736553335d717adcdf4b83ac8a8b3 + scheduling 0.1.0
HEAD a0ef8c5c26301a9f6950544afd0e070b7e691582 + scheduling 0.2.0
```

Итог для обоих вариантов:

```text
точный date resolver
редактирование availability
service management
scheduling 0.3.0
Alembic 0006
nails-db unchanged
Docker daemon unchanged
```

Deployment создаёт database/runtime backups, обновляет только `nails-api`, plugin и skills, проверяет OpenAPI/actions и не меняет calendar/service data.

## 6. Acceptance

После combined deployment:

1. Проверить ближайшую пятницу: 17 июля 2026.
2. Исправить 17/18 июля через подтверждаемую сводку.
3. Проверить неизменность 14/15 июля.
4. Изменить цену услуги без onboarding.
5. Проверить применение новой цены только к будущим bookings.
6. Проверить archive/reactivate без удаления истории.
7. Выполнить финальную read-only проверку counts и log privacy.
8. Закрыть Issue #34 после всех критериев.

Старый тест `Что у меня 18 июля?` с ожиданием рабочего интервала отменён.
