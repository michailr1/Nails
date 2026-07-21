# Nails — текущий контекст

Дата фиксации: **21 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Базовое состояние

```text
repository: michailr1/Nails
GitHub main: перепроверять через GitHub API; docs-only commits могут быть новее application release
production application release SHA: aae810ab0413a5a6448c2f4781380c83b2de28e1
runtime WEB SHA: aae810ab0413a5a6448c2f4781380c83b2de28e1
production host: de.funti.cc
public master portal: https://de.funti.cc:8446/web/
production repo: /opt/nails/repo
production branch: main
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
loopback web: http://127.0.0.1:8220/web/
health: /health
readiness: /ready
timezone: Europe/Moscow
Hermes plugins: nails-onboarding, nails-scheduling
finalization digest timer: enabled, active
Alembic: 0013 (head)
```

Основной агент пишет код, тесты и документацию, управляет GitHub, CI и review. VPS-агент только выполняет утверждённые deployment-команды и диагностику.

Обязательные правила:

- один живой Telegram-тест за раз;
- роли только `master`, `admin`, `client`;
- имя помощника — «Нэйли»;
- Нэйли — личная помощница мастера, а не CRM;
- пользовательский язык и сценарии определяются `docs/product/product-principles.md`;
- основной пользовательский раздел каталога называется **«Мой прайс»**, а не «Услуги»;
- интерфейс проектируется от ментальной модели мастера, техническая модель скрывается внутри системы;
- каждая мутация требует подтверждения;
- успех определяется только подтверждённым tool-результатом;
- PR-кандидат до merge запускается только из `origin/pr/<number>` и не меняет production checkout;
- отдельного finalize entrypoint нет;
- production release выполняется единым `NAILS_RELEASE_REF=origin/main bash ops/deploy/deploy.sh <exact-main-SHA>`;
- deploy выполняется только через `ops/deploy/deploy.sh <exact-SHA>`; ручное разделение его шагов запрещено;
- пользовательские ссылки на кабинет используют внешний TLS endpoint `https://de.funti.cc:8446/web/`.

## Завершённый production-этап

PR #167 добавил web-сценарий записи:

- создание записи из календаря;
- выбор существующей клиентки или быстрое добавление новой;
- основную процедуру и несколько дополнений из «Моего прайса»;
- индивидуальную итоговую цену и время;
- подтверждение полной сводки;
- идемпотентность и проверенный ответ;
- полную информацию при пересечении: клиентка, процедура, дополнения, фактическое время и занятый интервал с учётом времени до/после.

PR #168 добавил редактирование карточек клиенток в web:

- компактный список и открытие одной карточки;
- имя, телефон, день рождения и удобный способ связи;
- заметки, состояние ногтей и кожи, чувствительность;
- предпочтения по стилю и общению;
- обязательное подтверждение изменений;
- owner-scoped мутацию поверх существующего доменного `replace_client`;
- сохранение скрытого `private_alias`.

PR #169 добавил явное действие **«Свернуть»** в раскрытую позицию «Моего прайса». Сворачивание не выполняет серверную мутацию, сохраняет локальный черновик и возвращает компактную карточку в видимую область.

Production verification PR #169:

```text
DEPLOY_OK=true
sha=aae810ab0413a5a6448c2f4781380c83b2de28e1
prev_sha=1b89628db583c1b5bb40d2baa32dfaa9a265f9dc
running_web_sha=aae810ab0413a5a6448c2f4781380c83b2de28e1
final_checkout_sha=aae810ab0413a5a6448c2f4781380c83b2de28e1
api_health=200
api_readiness=200
loopback_web=200
production_working_tree_clean=true
PR169_PRODUCTION_OK=true
```

## Реальный прайс и модель

Получены фотографии реального прайса мастера с разделами «Маникюр», «Педикюр», «Дополнительно», «Дизайн» и «Парафинотерапия».

Зафиксировано:

- текущая ADR-007-модель уже покрывает реальные данные: `base`, `addon`, фиксированная цена, диапазон, цена за единицу и цена после уточнения;
- обозначения через `/` переносятся отдельными понятными позициями, а не новой технической моделью вариантов;
- дизайн `50/100 за 1 ноготь` хранится как цена за единицу; количество ногтей остаётся вне текущего scope, а итог можно уточнить для конкретной записи;
- зависимость цены от состояния стоп моделируется диапазоном;
- матрица совместимости дополнений с конкретными процедурами пока не вводится;
- пользовательские названия и категории меняются, backend-терминология `service/category/addon` остаётся без изменений;
- готовые предустановленные услуги в продукт не добавляются: перенос выполняется только в прайс выбранного мастера.

## Перенос реального прайса завершён

Read-only dry-run полного каталога был подтверждён владельцем. Затем штатный NAILS-002F backup прошёл gzip-проверку и isolated restore-test на Alembic `0013`. Подтверждённый payload применён через owner-scoped доменный `replace_catalog`, без прямых SQL-изменений.

```text
payload_sha256=cfdff556d17ee2cf31781dac91fd7bf33023e668daabe28a26c5960babd0ba77
replace_changed=true
created_count=33
updated_count=0
archived_count=1
target_active_service_count=33
non_target_catalogs_unchanged=true
fresh_readback_verified=true
DOMAIN_REPLACE_OK=true
backup_file=nails-20260721T165812Z.sql.gz
backup_alembic=0013
backup_verified=true
api_health=200
api_readiness=200
production_checkout_unchanged=true
production_working_tree_clean=true
NASTYA_PRICE_TRANSFER_OK=true
```

Итог:

- создано 33 позиции реального прайса;
- одна старая тестовая позиция архивирована;
- каталоги остальных мастеров не изменились;
- production checkout, application runtime и working tree не менялись;
- идентификатор production-учётной записи не хранится в документации.

Модель времени первоначального переноса:

- рабочее время основных процедур примерно на 10–15% меньше первоначальной консервативной оценки и округлено до 5 минут;
- 15 минут после самостоятельной процедуры остаются отдельным резервом на уборку и подготовку;
- короткие дополнения не уменьшались и увеличивают запись через `extra_minutes`;
- «Снятие без последующей процедуры» остаётся самостоятельной основной процедурой;
- простой и сложный дизайн, а также ремонт одного уголка используют цену за единицу;
- диапазоны сохранены там, где стоимость зависит от состояния стоп;
- итоговые цена и время конкретной записи могут быть уточнены мастером в форме записи.

## Приёмка этапа

Владелец проекта принял текущий web-контур и перенос реального прайса без отдельной ручной приёмки пилотным мастером. Такая приёмка отложена и не блокирует дальнейший roadmap. Новые пожелания по реальному прайсу или кабинету оформляются отдельными follow-up задачами, а не возвращают ADR-007 в активную разработку.

Issue #122 закрыт как выполненный. PR #170 зафиксировал production-факты и точку продолжения.

## Текущая задача

Начат ADR-004 — отдельный детерминированный клиентский Telegram-контур без LLM.

Активный implementation issue: **#171**.

Первый шаг:

1. зафиксировать проверенную инвентаризацию существующего Booking API;
2. определить минимальную owner-scoped клиентскую identity отдельно от операторских `users`;
3. определить заявку как отдельную сущность, не резервирующую время;
4. разбить реализацию на backend foundation, кабинет мастера, deterministic bot и управление своими заявками;
5. не начинать runtime client bot до принятия backend security contract.

## Следующий приоритет

ADR-004 Slice A — backend foundation:

- owner-scoped привязка Telegram-клиентки к существующей карточке `Client`;
- отдельная заявка со статусами `pending/approved/rejected/cancelled`;
- публичное read-only представление прайса и свободных окон;
- client create/list/cancel собственных заявок;
- master list/approve/reject через существующий `create_booking`;
- isolation, privacy, idempotency, audit и overlap regression tests;
- expand-only миграция с включением новых таблиц в backup/restore contract.

## Точка продолжения

```text
production_application_release_sha=aae810ab0413a5a6448c2f4781380c83b2de28e1
runtime_web_sha=aae810ab0413a5a6448c2f4781380c83b2de28e1
production_verification=DEPLOY_OK=true; PR169_PRODUCTION_OK=true
price_transfer=accepted; NASTYA_PRICE_TRANSFER_OK=true; 33 active; 1 archived; other catalogs unchanged
manual_pilot_master_acceptance=deferred; future wishes become follow-up issues
completed_issue=122
active_issue=171
active_task=ADR-004 implementation plan and client backend foundation
client_contour_source_of_truth=docs/decisions/ADR-004-client-contour-without-llm.md
product_source_of_truth=docs/product/product-principles.md
public_master_portal=https://de.funti.cc:8446/web/
release_contract=exact PR head candidate before merge; merged main uses one atomic deploy.sh flow
next=merge ADR-004 implementation plan, then implement Slice A backend foundation
```
