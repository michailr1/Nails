# Фактическое состояние проекта

Дата актуализации: **14 июля 2026 года**.

Для продолжения сначала читать [`context/current.md`](context/current.md).

## 1. Сводка

| Область | Состояние |
|---|---|
| Production repository | `385a92962e3736553335d717adcdf4b83ac8a8b3`, clean после последнего deployment |
| GitHub code fix | PR #44 merged, `c9e400c80398bd4367aad0ed0416ee0fc6a79b2d` |
| Backend API/PostgreSQL | production, healthy/ready |
| Alembic | `0006` |
| Hermes gateway | production, active |
| Onboarding plugin | production `0.5.0` |
| Scheduling plugin | production `0.1.0`; merged candidate `0.2.0` |
| Last deployment | `NAILS_002E4_V3_DEPLOYMENT_OK` |
| Next deployment | NAILS-002E5 runbook candidate |
| Telegram happy-path acceptance | приостановлена до E5 deployment |
| Active issue | Issue #34 |

## 2. Production baseline

```text
hostname: de.funti.cc
repo: /opt/nails/repo
HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3
backend API: http://127.0.0.1:8210
Alembic: 0006
gateway: active
```

Containers:

```text
nails-api
nails-db
```

Hermes управляется root user-level systemd, не Docker и не system-level systemd.

## 3. Найденные acceptance defects

### Неверное разрешение даты

Агент преобразовал «пятница» в `18 июля 2026`, хотя это суббота. Правильная ближайшая пятница — `17 июля 2026`.

Причина: модель вычисляла абсолютную дату до backend-вызова.

### Нельзя исправить график

Scheduling plugin `0.1.0` не содержит write operation для availability. Агент предложил пройти completed onboarding заново. Такой flow признан неприемлемым.

## 4. Смёрженное исправление

```text
PR #44
merge SHA: c9e400c80398bd4367aad0ed0416ee0fc6a79b2d
candidate scheduling plugin: 0.2.0
```

Trusted date resolver:

```text
POST /api/v1/scheduling/date/resolve
action=resolve_date
```

Он поддерживает полную дату, день/месяц без года, относительные даты, weekday occurrences, переход года и leap-day. Skills запрещают модели самостоятельно вычислять дату, год и день недели.

Direct availability management:

```text
PUT /api/v1/scheduling/availability
action=update_availability
```

Состояния:

```text
available
unavailable
unknown
```

Операция:

- меняет только явно названные даты;
- сохраняет остальные даты;
- требует сводку и подтверждение;
- атомарна и идемпотентна;
- защищает active bookings;
- не изменяет completed onboarding.

PR #44 checks:

```text
Agent responsibility contract #25 — success
Production infrastructure contract #14 — success
CI #115 — success
backend — success
onboarding plugin 3.11/3.12 — success
scheduling plugin 3.11/3.12 — success
compose-smoke — success
review threads — none
```

## 5. Правильный regression scenario

```text
2026-07-14 11:00–20:00 — сохранить
2026-07-15 11:00–20:00 — сохранить
2026-07-17 11:00–15:00 — добавить
2026-07-18 — удалить как ошибочную дату, state=unknown
```

`unknown` не означает выходной и не означает свободный день.

## 6. Старый тест отменён

```text
Что у меня 18 июля?
```

Ожидание рабочего интервала `11:00–15:00` признано основанным на ошибочных данных. Старый acceptance не продолжать.

## 7. NAILS-002E5 deployment candidate

```text
branch: ops/nails-002e5-date-availability
entrypoint: ops/deploy/nails-002e5-date-availability.sh
success marker: NAILS_002E5_DEPLOYMENT_OK
```

Runbook должен:

- проверить exact production baseline и release SHA;
- доказать отсутствие Alembic file changes;
- создать PostgreSQL и runtime backups;
- build нового API image до остановки gateway;
- пересоздать только `nails-api`;
- сохранить `nails-db` и Docker daemon без изменений;
- сохранить Alembic `0006`;
- установить scheduling plugin `0.2.0` и оба skills;
- не менять Hermes config;
- проверить OpenAPI routes, registry, Telegram actions и журналы;
- восстановить старый API image/runtime/repo/gateway при ошибке;
- не выполнять SQL и не менять calendar data.

API container ожидаемо изменится. DB container и Docker daemon должны остаться прежними.

## 8. Следующая production-приёмка

После успешного E5 deployment:

1. «Какая дата у ближайшей пятницы?» → `17 июля 2026`, пятница.
2. «Исправь график: 17 июля работаю 11:00–15:00, ошибочную 18 июля убери».
3. Проверить «сейчас → будет» и отсутствие write до подтверждения.
4. Подтвердить.
5. Проверить: 17 July available, 18 July unknown, 14/15 unchanged.
6. Только затем продолжить free slots/client/booking acceptance.
7. Выполнить финальную read-only проверку counts и log privacy.
8. Закрыть Issue #34 после всех критериев.
