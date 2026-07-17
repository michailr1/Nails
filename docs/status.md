# Фактическое состояние проекта

Дата актуализации: **17 июля 2026 года**.

Для продолжения сначала читать [`context/current.md`](context/current.md).

## 1. Сводка

| Область | Состояние |
|---|---|
| GitHub `main` | `847a6342911b5bf32a9e6c0885065e161c6d2d06` |
| Production API/PostgreSQL | healthy/ready |
| API bind | `127.0.0.1:8210` |
| Health endpoints | `/health`, `/ready` |
| Alembic | `0008` |
| Hermes gateway | active |
| Shutdown/restart Telegram notification | disabled только для profile `nails` |
| Backup/restore | NAILS-002F завершён и принят в production |
| Pilot | завершён после живой проверки двумя мастерами |
| NAILS-003 | завершён: preview, несколько окон и ADR-006 в production |
| Следующий этап | web-интерфейс мастера |
| После web | клиентский контур ADR-004 |

## 2. Что уже работает

- onboarding только для первичного заполнения;
- изменение настроек мастера без повторного onboarding;
- услуги: создание, изменение, архив и восстановление;
- точное разрешение дат;
- доступность по конкретным датам и несколько интервалов в день;
- read-only preview изменения доступности;
- исправление и снятие сохранённой настройки даты;
- целый выходной с защитой существующих записей;
- просмотр дня и свободных окон;
- клиентские карточки с расширенными private fields;
- exact/candidate поиск и защита от случайных дублей;
- создание записей с snapshots;
- корректный перенос без самоблокировки;
- мягкая отмена;
- fresh-read/readback и verified guarded mutations;
- ежедневные backup + isolated restore-test + retention + Telegram archive;
- защищённое сохранение негативного feedback.

## 3. Завершённый NAILS-003

Фактический источник настройки окон — `availability_intervals`. Параллельные `schedule_rules` или `schedule_exceptions` не создавались.

Рабочий flow:

```text
resolve_date
→ day_view
→ preview_availability
→ понятная сводка «сейчас → будет»
→ явное подтверждение
→ update_availability
→ day_view readback
```

`preview_availability` принимает тот же итоговый набор интервалов, что write, и возвращает текущее/предлагаемое состояние, `changed`, `can_apply` и конфликты. Preview read-only. Write owner-scoped, audited, подтверждаемый и идемпотентный.

Частичное закрытие дня уже поддерживается как преобразование положительных окон, например:

```text
11:00–20:00
→ 11:00–13:00 + 16:00–20:00
```

Исправление выполняется новой заменой итоговых окон; снятие настройки — `state=unknown`; целый выходной — `state=unavailable`.

## 4. Семантика ADR-006

Явно названное мастером время открыто по умолчанию.

Прямая запись отклоняется только при:

- явно сохранённом целом выходном;
- overlap с активной записью с учётом reserved intervals и buffers.

Положительные интервалы и диапазон подсказок `10:00–23:00` не являются жёстким запретом. Они формируют только предлагаемые свободные окна. Поэтому жёсткие частичные блоки сознательно не входят в текущую модель.

## 5. Production acceptance

Для SHA `847a6342911b5bf32a9e6c0885065e161c6d2d06` подтверждено:

```text
running_sha=847a6342911b5bf32a9e6c0885065e161c6d2d06
working_tree_clean=true
nails-api=running
container_health=healthy
api_bind=127.0.0.1:8210
GET /health=200
GET /ready=200
gateway_active=true
```

## 6. Следующий этап

Web-интерфейс мастера начинается до клиентского контура.

Сначала нужно сверить ADR-005 с текущими backend-инвариантами, определить минимальный implementation issue и не дублировать бизнес-логику Telegram-контура в web.
