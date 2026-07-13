# Фактическое состояние проекта

Дата актуализации: **14 июля 2026 года**.

Для продолжения сначала читать [`context/current.md`](context/current.md).

## 1. Сводка

| Область | Состояние |
|---|---|
| Production repository | `HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3`, последний доказанный clean state |
| Backend API/PostgreSQL | healthy/ready по последнему production-отчёту |
| Alembic | `0006` |
| Hermes gateway | active по последнему production-отчёту |
| Onboarding plugin | production `0.5.0` |
| Scheduling plugin | доказанный production `0.1.0`; E5 candidate `0.2.0`; service-management candidate `0.3.0` |
| Date/availability fix | PR #44 merged, `c9e400c80398bd4367aad0ed0416ee0fc6a79b2d` |
| E5 runbook | PR #45 merged, release `a0ef8c5c26301a9f6950544afd0e070b7e691582` |
| Service management | PR #46 open, not deployed |
| Last proven deployment | `NAILS_002E4_V3_DEPLOYMENT_OK` |
| E5 production result | не получен |
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

До получения VPS-вывода нельзя утверждать, что E5 уже развернул plugin `0.2.0`.

## 3. Найденные UX-дефекты

1. Модель неверно сопоставила пятницу с 18 июля 2026 года вместо 17 июля.
2. Изменение графика требовало повторного onboarding.
3. Изменение услуги, цены, длительности или buffers также требовало повторного onboarding.

Общий продуктовый вывод:

> Onboarding — только мастер первичного заполнения. После завершения рабочие данные должны редактироваться через restricted domain operations.

## 4. PR #44 merged — даты и availability

```text
PR #44 merged
merge SHA: c9e400c80398bd4367aad0ed0416ee0fc6a79b2d
candidate `0.2.0`
```

Добавлено:

```text
resolve_date
update_availability
```

Дата и weekday вычисляются backend. График меняется по конкретным датам без повторного onboarding.

## 5. NAILS-002E5

```text
release SHA: a0ef8c5c26301a9f6950544afd0e070b7e691582
entrypoint: ops/deploy/nails-002e5-date-availability.sh
success marker: NAILS_002E5_DEPLOYMENT_OK
```

Runbook должен обновить API и scheduling plugin до `0.2.0`, не меняя Alembic `0006`, `nails-db`, Docker daemon или calendar data.

Фактический результат deployment пока не получен. Не запускать acceptance и не продвигать `main` до проверки E5, потому что runbook требует exact `origin/main` release SHA.

## 6. PR #46 — service management

```text
branch: feat/service-management
plugin candidate: 0.3.0
production deployed: false
migration: none
```

Новые operations:

```text
find_service
create_service
update_service
```

Поддерживается:

- создание услуги после onboarding;
- изменение названия и описания;
- изменение цены и валюты;
- изменение длительности и buffers;
- просмотр архивных услуг;
- архивация и восстановление.

Безопасность:

- exact owner-scoped lookup;
- «сейчас → будет» и явное подтверждение;
- repeat-safe create/update;
- name-conflict protection;
- физического удаления нет;
- существующие bookings сохраняют price/currency/duration/buffer snapshots;
- новые параметры применяются только к будущим bookings;
- архив блокирует новые записи, но не удаляет историю.

Scheduling plugin tests проходят на Python 3.11/3.12 после обновления read-контракта. Backend и compose-smoke должны пройти финальный обычный CI.

## 7. Правильный calendar regression scenario

```text
2026-07-14 11:00–20:00 — сохранить
2026-07-15 11:00–20:00 — сохранить
2026-07-17 11:00–15:00 — добавить
2026-07-18 — state=unknown
```

Старый тест `Что у меня 18 июля?` и ожидание рабочего интервала признаны ошибочными.

## 8. Порядок продолжения

1. Получить полный green CI PR #46 и проверить review threads.
2. Получить от пользователя фактический E5 VPS output.
3. Проверить `NAILS_002E5_DEPLOYMENT_OK` или rollback.
4. Выполнить date/availability Telegram acceptance по одному сообщению.
5. Только после E5 продвинуть `main`, merge PR #46 и подготовить отдельный service-management deployment runbook.
6. После его deployment проверить изменение цены/длительности/buffers без onboarding.
7. Выполнить финальную read-only проверку counts и log privacy.
8. Закрыть Issue #34 после всех критериев.
