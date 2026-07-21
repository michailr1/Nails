# Фактическое состояние проекта

Дата актуализации: **21 июля 2026 года**.

Для продолжения сначала читать [`context/current.md`](context/current.md). GitHub `main` и production SHA там разделены: docs-only commits могут быть новее application runtime.

## 1. Сводка

| Область | Состояние |
|---|---|
| Production application/runtime | `aae810ab0413a5a6448c2f4781380c83b2de28e1` |
| Production API/PostgreSQL | healthy/ready |
| API bind | `127.0.0.1:8210` |
| Master web | `https://de.funti.cc:8446/web/` |
| Health endpoints | `/health`, `/ready` |
| Alembic | `0013` |
| Hermes gateway | active |
| Shutdown/restart Telegram notification | disabled только для profile `nails` |
| Backup/restore | NAILS-002F завершён и принят в production |
| Pilot | завершён после живой проверки двумя мастерами |
| NAILS-003 | завершён: preview, несколько окон и ADR-006 в production |
| Master Web UI | принят владельцем; отдельная приёмка пилотным мастером отложена |
| ADR-007 | завершён; реальный прайс перенесён |
| Active issue | #171 — ADR-004 client contour |
| Текущий этап | backend foundation детерминированного клиентского Telegram-бота |

## 2. Что уже работает

### Telegram-контур мастера

- onboarding только для первичного заполнения;
- изменение настроек мастера без повторного onboarding;
- «Мой прайс»: создание, изменение, удаление из прайса и восстановление;
- точное разрешение дат;
- доступность по конкретным датам и несколько интервалов в день;
- read-only preview изменения доступности;
- исправление и снятие сохранённой настройки даты;
- целый выходной с защитой существующих записей;
- просмотр дня и свободных окон;
- клиентские карточки с расширенными private fields;
- exact/candidate поиск и защита от случайных дублей;
- создание записей с snapshots и дополнениями;
- корректный перенос без самоблокировки;
- мягкая отмена;
- финализация визита и вечерний дайджест;
- fresh-read/readback и verified guarded mutations;
- защищённое сохранение негативного feedback.

### Кабинет мастера

- вход с Telegram-подтверждением;
- календарь дня, недели и месяца;
- owner-scoped CSV/XLSX выгрузки;
- компактный экран «Мой прайс» по разделам;
- fixed/range/per-unit/on-request цены;
- создание записи с основной процедурой и дополнениями;
- быстрое добавление клиентки;
- просмотр и редактирование полной пользовательской части карточки клиентки;
- подтверждения мутаций, idempotency и fresh readback;
- same-origin BFF без публикации внутреннего Booking API.

### Надёжность

- ежедневные backup;
- isolated restore-test;
- retention daily/weekly/monthly/runtime;
- Telegram archive администратора;
- backup перед мутирующим deploy;
- exact PR-head candidate до merge;
- единый main deploy через `ops/deploy/deploy.sh`;
- rollback как deploy предыдущего SHA.

## 3. Принятый реальный прайс

Подтверждённый owner-scoped перенос:

```text
payload_sha256=cfdff556d17ee2cf31781dac91fd7bf33023e668daabe28a26c5960babd0ba77
created_count=33
updated_count=0
archived_count=1
target_active_service_count=33
non_target_catalogs_unchanged=true
fresh_readback_verified=true
backup_alembic=0013
backup_verified=true
NASTYA_PRICE_TRANSFER_OK=true
```

Отдельная ручная приёмка пилотным мастером отложена. Этап принят владельцем; новые пожелания оформляются отдельными follow-up задачами.

## 4. Семантика ADR-006

Явно названное мастером время открыто по умолчанию.

Прямая запись отклоняется только при:

- явно сохранённом целом выходном;
- overlap с активной записью с учётом reserved intervals и buffers.

Положительные интервалы и диапазон подсказок не являются жёстким запретом. Они формируют только предлагаемые свободные окна.

## 5. Следующий этап — ADR-004

Клиентский контур первой версии:

- отдельный deterministic Telegram bot без LLM и без публичного Hermes;
- client identity отделена от доверенных `admin|master` users;
- клиентка видит публичный прайс, свободные окна и только свои заявки/записи;
- отправленная клиенткой заявка не резервирует время;
- мастер подтверждает или отклоняет заявку;
- подтверждение создаёт обычный Booking через существующий доменный `create_booking` и повторно проверяет overlap;
- private aliases и notes наружу не выводятся;
- первый запуск рассчитан на одного мастера.

Implementation issue: **#171**.

Первый рабочий срез — backend foundation и security contracts до подключения bot runtime.
