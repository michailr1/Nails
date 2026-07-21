# Nails — текущий контекст

Дата фиксации: **21 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Базовое состояние

```text
repository: michailr1/Nails
GitHub main: 1b89628db583c1b5bb40d2baa32dfaa9a265f9dc на момент создания текущей ветки; всегда перепроверять через GitHub API
последний независимо подтверждённый production application release SHA: 6580dbda77dee7f0480504c51a38f9d7b6b91a23
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

## Завершённые изменения в GitHub main

PR #167 добавил web-сценарий записи:

- создание записи из календаря;
- выбор существующей клиентки или быстрое добавление новой;
- основную процедуру и несколько дополнений из «Моего прайса»;
- индивидуальную итоговую цену и время;
- подтверждение полной сводки;
- идемпотентность и проверенный ответ;
- полную информацию при пересечении: клиентка, процедура, дополнения, фактическое время и занятый интервал с учётом времени до/после.

Последний независимо подтверждённый production report относится к PR #167: `DEPLOY_OK=true`, checkout и runtime WEB совпадали с `6580dbda77dee7f0480504c51a38f9d7b6b91a23`, working tree был clean.

PR #168 добавил редактирование карточек клиенток в web:

- компактный список и открытие одной карточки;
- имя, телефон, день рождения и удобный способ связи;
- заметки, состояние ногтей и кожи, чувствительность;
- предпочтения по стилю и общению;
- обязательное подтверждение изменений;
- owner-scoped мутацию поверх существующего доменного `replace_client`;
- сохранение скрытого `private_alias`.

Факт production deployment GitHub main `1b89628d…` в этом контексте ещё не подтверждён отдельным preflight/report и не должен предполагаться.

## Реальный прайс и модель

Получены фотографии реального прайса мастера с разделами «Маникюр», «Педикюр», «Дополнительно», «Дизайн» и «Парафинотерапия».

Зафиксировано:

- текущая ADR-007-модель уже покрывает реальные данные: `base`, `addon`, фиксированная цена, диапазон, цена за единицу и цена после уточнения;
- обозначения через `/` переносятся отдельными понятными позициями, а не новой технической моделью вариантов;
- дизайн `50/100 за 1 ноготь` хранится как цена за единицу; количество ногтей остаётся вне текущего scope, а итог можно уточнить для конкретной записи;
- зависимость цены от состояния стоп моделируется диапазоном;
- матрица совместимости дополнений с конкретными процедурами пока не вводится.

## Текущая задача

Ветка `fix/web-price-editor-collapse` от GitHub main SHA `1b89628db583c1b5bb40d2baa32dfaa9a265f9dc` исправляет мобильный сценарий «Моего прайса»:

- раскрытая позиция получает явную кнопку **«Свернуть»** рядом с действием удаления;
- сворачивание возвращает компактную карточку без сохранения на сервер и без потери локального черновика;
- после сворачивания компактная карточка остаётся в видимой области;
- отдельный regression-тест фиксирует наличие кнопки и обработчика;
- новых API, таблиц, миграций и доменных механизмов нет.

## Следующий приоритет

1. Завершить `fix/web-price-editor-collapse`: PR → review → green CI → exact-head candidate → ручная проверка на телефоне → merge → production deploy.
2. Перенести реальный прайс мастера через существующий подтверждаемый batch replace, разделяя варианты через `/` на отдельные позиции.
3. После живой работы уточнить только реальные пробелы: количество для цены за единицу и применимость дополнений.

## Точка продолжения

```text
github_main_sha_at_branch_creation=1b89628db583c1b5bb40d2baa32dfaa9a265f9dc
last_independently_verified_production_sha=6580dbda77dee7f0480504c51a38f9d7b6b91a23
active_branch=fix/web-price-editor-collapse
product_source_of_truth=docs/product/product-principles.md
pricing_source_of_truth=docs/decisions/ADR-007-service-catalog-and-pricing.md
public_master_portal=https://de.funti.cc:8446/web/
release_contract=exact PR head candidate before merge; merged main uses one atomic deploy.sh flow
next=review and finish explicit price editor collapse, then move the real master price
```
