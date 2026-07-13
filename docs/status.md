# Фактическое состояние проекта

Дата актуализации: **14 июля 2026 года**.

Для продолжения сначала читать [`context/current.md`](context/current.md).

## 1. Сводка

| Область | Состояние |
|---|---|
| Production repository | `385a92962e3736553335d717adcdf4b83ac8a8b3`, clean после последнего deployment |
| GitHub main | `5c1d4d73f58851c5fb20c36dca7d591ff3f96583` до merge активного fix PR |
| Backend API/PostgreSQL | production, healthy/ready |
| Alembic | `0006` |
| Hermes gateway | production, active |
| Onboarding plugin | production `0.5.0` |
| Scheduling plugin | production `0.1.0`; candidate `0.2.0` в PR #44 |
| Telegram visibility | `nails_onboarding`, `nails_scheduling` |
| Last deployment | `NAILS_002E4_V3_DEPLOYMENT_OK` |
| Telegram happy-path acceptance | приостановлена после найденных blocking defects |
| Active issue | Issue #34 |

## 2. Production

```text
hostname: de.funti.cc
repo: /opt/nails/repo
HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3
backend API: http://127.0.0.1:8210
Alembic: 0006
gateway: active
```

Backend containers:

```text
nails-api
nails-db
```

Hermes управляется root user-level systemd, не Docker и не system-level systemd.

## 3. Успешно внедрённый baseline

Последний runbook:

```text
ops/deploy/nails-002e4-v3.sh
NAILS_002E4_V3_DEPLOYMENT_OK
```

Production содержит:

- onboarding plugin `0.5.0`;
- scheduling plugin `0.1.0`;
- чтение услуг и дня;
- поиск свободных окон;
- exact client lookup;
- подтверждаемое создание клиентки;
- подтверждаемое создание записи;
- owner-scoped trusted Telegram identity;
- buffers, overlap protection и idempotency.

## 4. Найденные acceptance defects

### Неверное разрешение естественных дат

Агент преобразовал «пятница» в `18 июля 2026`, хотя это суббота. Правильная пятница — `17 июля 2026`.

Backend умеет вычислять `weekday_iso`, но модель угадывала абсолютную дату до вызова backend.

### Нельзя исправить график после onboarding

Scheduling plugin `0.1.0` не содержит write operation для availability. Агент предложил пройти completed onboarding заново, чтобы исправить одну дату.

Такой flow признан неприемлемым.

## 5. Активное исправление

```text
PR #44
branch: fix/date-resolution-schedule-editing
candidate scheduling plugin: 0.2.0
```

Добавляется trusted backend resolver:

```text
POST /api/v1/scheduling/date/resolve
action=resolve_date
```

Он поддерживает:

- полную дату;
- день/месяц без года;
- относительные даты;
- ближайший weekday;
- weekday текущей/следующей недели;
- переход года и leap-day.

Skills запрещают модели самостоятельно вычислять дату, год и день недели.

Добавляется direct availability management:

```text
PUT /api/v1/scheduling/availability
action=update_availability
```

Состояния даты:

```text
available
unavailable
unknown
```

Операция:

- меняет только явно названные даты;
- сохраняет остальные даты;
- требует сводку и подтверждение;
- атомарна;
- идемпотентна;
- защищает существующие записи;
- не изменяет completed onboarding.

## 6. Правильный regression scenario

```text
2026-07-14 11:00–20:00 — сохранить
2026-07-15 11:00–20:00 — сохранить
2026-07-17 11:00–15:00 — добавить
2026-07-18 — удалить как ошибочную дату, state=unknown
```

`unknown` не означает выходной и не означает свободный день.

## 7. Старый тест отменён

Предыдущий тест:

```text
Что у меня 18 июля?
```

и ожидание рабочего интервала `11:00–15:00` признаны основанными на ошибочных данных. До deployment PR #44 старый Telegram acceptance не продолжать.

## 8. Проверки PR #44

Backend regression tests покрывают:

- Friday → `2026-07-17`, `weekday_iso=5`;
- `18 июля` → `2026-07-18`, `weekday_iso=6`;
- next-week semantics;
- year rollover;
- leap-day;
- correction 17/18 July;
- сохранение 14/15 July;
- repeated update → `changed=false`;
- audit metadata;
- rejection, если изменение вытесняет active booking.

Plugin tests покрывают public schema, trusted identity, exact backend request shapes, response sanitization и confirmation requirements.

## 9. Deployment impact

После merge потребуется новый production runbook:

- exact release SHA;
- database backup;
- repository/runtime/skills backup;
- rebuild/recreate только `nails-api`;
- `nails-db` и Docker daemon unchanged;
- no migration, Alembic remains `0006`;
- scheduling plugin `0.2.0`;
- обновлённые onboarding/scheduling skills;
- restart только root user-level Hermes gateway;
- rollback backend/plugin/skills/repo/gateway при любой ошибке.

## 10. Следующая production-приёмка

После deployment:

1. «Какая дата у ближайшей пятницы?» → 17 июля 2026, пятница.
2. «Исправь график: 17 июля работаю 11:00–15:00, ошибочную 18 июля убери».
3. Проверить current → future summary и запрос подтверждения.
4. Подтвердить.
5. Проверить 17 July available, 18 July unknown, 14/15 unchanged.
6. Только затем продолжить free slots/client/booking acceptance.
7. Выполнить финальную read-only проверку counts и log privacy.
8. Закрыть Issue #34 после всех критериев.
