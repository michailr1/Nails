# Nails — текущий контекст

Дата фиксации: **21 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Базовое состояние

```text
repository: michailr1/Nails
GitHub main: 6580dbda77dee7f0480504c51a38f9d7b6b91a23 на момент создания текущей ветки; всегда перепроверять через GitHub API
production host: de.funti.cc
public master portal: https://de.funti.cc:8446/web/
production repo: /opt/nails/repo
production branch: main
production application release SHA: 6580dbda77dee7f0480504c51a38f9d7b6b91a23
runtime WEB SHA: 6580dbda77dee7f0480504c51a38f9d7b6b91a23
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

## Завершённый этап

На production развернут application release SHA `6580dbda77dee7f0480504c51a38f9d7b6b91a23` из PR #167.

Web-сценарий записи теперь поддерживает:

- создание записи из календаря;
- выбор существующей клиентки или быстрое добавление новой;
- основную процедуру и несколько дополнений из «Моего прайса»;
- индивидуальную итоговую цену и время;
- подтверждение полной сводки;
- идемпотентность и проверенный ответ;
- полную информацию при пересечении: клиентка, процедура, дополнения, фактическое время и занятый интервал с учётом времени до/после.

Production verification PR #167: `DEPLOY_OK=true`, checkout и runtime WEB совпадают с `6580dbda77dee7f0480504c51a38f9d7b6b91a23`, working tree clean.

## Реальный прайс и модель

Получены фотографии реального прайса мастера с разделами «Маникюр», «Педикюр», «Дополнительно», «Дизайн» и «Парафинотерапия».

Зафиксировано:

- текущая ADR-007-модель уже покрывает реальные данные: `base`, `addon`, фиксированная цена, диапазон, цена за единицу и цена после уточнения;
- обозначения через `/` переносятся отдельными понятными позициями, а не новой технической моделью вариантов;
- дизайн `50/100 за 1 ноготь` хранится как цена за единицу; количество ногтей остаётся вне текущего scope, а итог можно уточнить для конкретной записи;
- зависимость цены от состояния стоп моделируется диапазоном;
- матрица совместимости дополнений с конкретными процедурами пока не вводится.

## Текущая задача

Ветка `feat/web-client-cards` от production/main SHA `6580dbda77dee7f0480504c51a38f9d7b6b91a23` реализует редактирование карточек клиенток в web:

- компактный список клиенток;
- открытие одной карточки для изменения без административной таблицы;
- имя, телефон, день рождения и удобный способ связи;
- общие заметки;
- состояние ногтей и кожи;
- чувствительность и ограничения;
- предпочтения по стилю и общению;
- обязательное подтверждение с перечнем изменённых разделов;
- owner-scoped `PUT /web/api/clients/{client_id}` поверх существующего доменного `replace_client`;
- сохранение скрытого `private_alias`, который web не показывает и не должен затирать;
- проверенный ответ после мутации, audit и защита от дублирующего имени;
- миграций и нового доменного механизма нет.

## Следующий приоритет

1. Завершить `feat/web-client-cards`: PR → review → green CI → exact-head candidate → ручная проверка на телефоне → merge → production deploy.
2. Перенести реальный прайс мастера через существующий подтверждаемый batch replace, разделяя варианты через `/` на отдельные позиции.
3. После живой работы уточнить только реальные пробелы: количество для цены за единицу и применимость дополнений.

## Точка продолжения

```text
production_application_release_sha=6580dbda77dee7f0480504c51a38f9d7b6b91a23
active_branch=feat/web-client-cards
product_source_of_truth=docs/product/product-principles.md
pricing_source_of_truth=docs/decisions/ADR-007-service-catalog-and-pricing.md
public_master_portal=https://de.funti.cc:8446/web/
release_contract=exact PR head candidate before merge; merged main uses one atomic deploy.sh flow
next=review and finish editable web client cards, then move the real master price
```
