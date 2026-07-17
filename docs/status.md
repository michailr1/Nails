# Фактическое состояние проекта

Дата актуализации: **17 июля 2026 года**.

Для продолжения сначала читать [`context/current.md`](context/current.md).

## 1. Сводка

| Область | Состояние |
|---|---|
| GitHub `main` | `0c08ffcd06752e13b8fa1372058d1dce079c455e` |
| Production API/PostgreSQL | healthy/ready по последнему production-отчёту |
| Alembic | `0006` |
| Hermes gateway | active |
| Shutdown/restart Telegram notification | disabled только для profile `nails` |
| Backup/restore | NAILS-002F завершён и принят в production |
| Pilot | завершён после живой проверки двумя мастерами |
| Active issue | #104 — корректировка ограничений рабочего времени |
| Active PR | draft #105 — availability preview before mutation |
| Следующий порядок | рабочее время → web-интерфейс мастера → клиентский контур ADR-004 |

## 2. Что уже работает

- onboarding только для первичного заполнения;
- изменение настроек мастера без повторного onboarding;
- услуги: создание, изменение, архив и восстановление;
- точное разрешение дат;
- доступность по конкретным датам и несколько интервалов в день;
- просмотр дня и свободных окон;
- клиентские карточки с расширенными private fields;
- exact/candidate поиск и защита от случайных дублей;
- создание записей с snapshots;
- корректный перенос без самоблокировки;
- мягкая отмена;
- fresh-read/readback и verified guarded mutations;
- ежедневные backup + isolated restore-test + retention + Telegram archive.

## 3. Активный slice PR #105

Фактический источник рабочего времени — таблица `availability_intervals`. Новая таблица или миграция не добавляется.

PR #105 добавляет:

```text
POST /api/v1/scheduling/availability/preview
restricted action: preview_availability
```

Preview принимает тот же итоговый набор интервалов конкретных дат, что существующий `update_availability`, и возвращает:

- текущее состояние;
- предлагаемое состояние;
- `changed`;
- `can_apply`;
- конкретные конфликтующие scheduled bookings с учётом reserved intervals и buffers.

Preview является read-only и не требует `confirmed`. Write остаётся только в `update_availability`, который повторно выполняет server-side conflict check под owner schedule lock.

Обязательный skill-flow:

```text
resolve_date
→ day_view
→ preview_availability
→ понятная сводка «сейчас → будет»
→ явное подтверждение
→ update_availability
→ day_view readback
```

Если `can_apply=false`, write не выполняется. Существующие записи не переносятся и не отменяются автоматически.

## 4. Проверки PR #105

На head `660b0f2391294545e3d2972398e528906516a130` подтверждалось:

- backend Ruff, migrations и pytest — success;
- scheduling plugin Ruff — success;
- первое падение scheduling plugin pytest было вызвано устаревшим точным contract-ожиданием списка actions;
- contract обновлён и добавлен отдельный read-only preview tool test;
- agent responsibility contract — success;
- production infrastructure contract не запускается корректно, так как охраняемые path-filter файлы не менялись на этом head.

После обновления skill и документации требуется новый полный CI на финальном head.

## 5. Границы

PR #105:

- является первым отдельным инкрементом issue #104;
- не является полной реализацией issue #100 / ADR-006;
- не переводит scheduling на семантику «открыто по умолчанию»;
- не меняет `ensure_reservation_available`;
- не начинает web-интерфейс;
- не начинает клиентский контур.

## 6. До merge

1. Получить зелёный CI на финальном PR-head.
2. Проверить review threads и ff от свежего `main`.
3. Выполнить production candidate exact PR-head SHA через постоянный `ops/deploy/deploy.sh`.
4. Fast-forward merge только того же проверенного SHA.
5. Finalize production checkout.
6. Выполнить Telegram acceptance: preview → сводка → confirmation → update → readback.
