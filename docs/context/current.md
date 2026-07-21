# Nails — текущий контекст

Дата фиксации: **21 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Базовое состояние

```text
repository: michailr1/Nails
GitHub main: 4ac932bace27c67f31199dba52ad8f31a75cb04d на момент создания текущей ветки; всегда перепроверять через GitHub API
production host: de.funti.cc
public master portal: https://de.funti.cc:8446/web/
production repo: /opt/nails/repo
production branch: main
production application release SHA: 4ac932bace27c67f31199dba52ad8f31a75cb04d
runtime WEB SHA: 4ac932bace27c67f31199dba52ad8f31a75cb04d
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

На production развернут application release SHA `4ac932bace27c67f31199dba52ad8f31a75cb04d`.

PR #164–166 завершили первый удобный слой «Моего прайса»:

- компактный список по разделам;
- раскрытие одной позиции для редактирования;
- «Добавить в прайс», «Убрать из прайса» и «Вернуть в прайс»;
- несохранённая случайная позиция удаляется полностью;
- сохранённая позиция архивируется без потери истории;
- необязательное поле «Описание» скрыто из формы, но `public_description` сохранено в backend/API и не затирается при других изменениях.

Production verification PR #166: `DEPLOY_OK=true`, checkout и runtime WEB совпадают с `4ac932bace27c67f31199dba52ad8f31a75cb04d`, working tree clean.

## Реальный прайс и модель

Получены фотографии реального прайса мастера с разделами «Маникюр», «Педикюр», «Дополнительно», «Дизайн» и «Парафинотерапия».

Зафиксировано:

- текущая ADR-007-модель уже покрывает реальные данные: `base`, `addon`, фиксированная цена, диапазон, цена за единицу и цена после уточнения;
- обозначения через `/` переносятся отдельными понятными позициями, а не новой технической моделью вариантов;
- дизайн `50/100 за 1 ноготь` хранится как цена за единицу; количество ногтей остаётся вне текущего scope, а итог можно уточнить для конкретной записи;
- зависимость цены от состояния стоп моделируется диапазоном;
- матрица совместимости дополнений с конкретными процедурами пока не вводится;
- следующий реальный пробел — web-сценарий записи «основная процедура + дополнения», а не новая схема БД.

## Текущая задача

Ветка `feat/web-booking-composer` от production/main SHA `4ac932bace27c67f31199dba52ad8f31a75cb04d` реализует первый web write-slice создания записи:

- owner-scoped `POST /web/api/bookings` поверх существующего доменного `create_booking`;
- обязательные session и Origin/Host boundary;
- idempotency key и server-side повторная проверка;
- выбор существующей клиентки, основной процедуры и нескольких дополнений;
- прогрессивно раскрываемые overrides итоговой цены и времени;
- подтверждение полной сводки до мутации;
- fresh verified response и повторное чтение календаря;
- честное отображение диапазона и неизвестной/поединичной цены вместо ложных `0 ₽`;
- browser получает только web-представление записи, без внутренних ID состава каталога;
- миграций и изменения доменной booking-модели нет.

## Следующий приоритет

1. Завершить `feat/web-booking-composer`: PR → review → green CI → exact-head candidate → ручная проверка → merge → production deploy.
2. Перенести реальный прайс мастера через уже существующий подтверждаемый batch replace, разделяя варианты через `/` на отдельные позиции.
3. После живой работы уточнить только реальные пробелы: количество для цены за единицу и применимость дополнений.

## Точка продолжения

```text
production_application_release_sha=4ac932bace27c67f31199dba52ad8f31a75cb04d
active_branch=feat/web-booking-composer
product_source_of_truth=docs/product/product-principles.md
pricing_source_of_truth=docs/decisions/ADR-007-service-catalog-and-pricing.md
public_master_portal=https://de.funti.cc:8446/web/
release_contract=exact PR head candidate before merge; merged main uses one atomic deploy.sh flow
next=open and review web booking composer PR, fix CI, then request only candidate/manual acceptance
```
