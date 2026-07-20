# Nails — текущий контекст

Дата фиксации: **20 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Базовое состояние

```text
repository: michailr1/Nails
GitHub main: всегда проверять через GitHub API; после production release может содержать более новые docs-only commits
production host: de.funti.cc
public master portal: https://de.funti.cc:8446/web/
production repo: /opt/nails/repo
production branch: main
production application release SHA: 01fe8547e9038c098b4f4ea22f449622d4b774ea
runtime API SHA: 01fe8547e9038c098b4f4ea22f449622d4b774ea
runtime WEB SHA: 01fe8547e9038c098b4f4ea22f449622d4b774ea
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
loopback web: http://127.0.0.1:8220/web/
health: /health
readiness: /ready
timezone: Europe/Moscow
Hermes plugins: nails-onboarding, nails-scheduling
finalization digest timer: enabled, active
last verified backup: /opt/nails/backups/nails-before-deploy-20260720T145208Z.sql.gz
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
- после merge отдельного finalize entrypoint нет: production release выполняется единым `NAILS_RELEASE_REF=origin/main bash ops/deploy/deploy.sh <exact-main-SHA>`;
- штатный main deploy создаёт и валидирует backup, собирает и проверяет runtime, выполняет миграции и health/readiness, затем fast-forward’ит локальный checkout и возвращает `DEPLOY_OK=true`;
- deploy выполняется только через `ops/deploy/deploy.sh <exact-SHA>`; ручное разделение его шагов запрещено;
- docs-only commits после release не означают, что application runtime отстал: сравнивать нужно последний production application release SHA и фактически работающие API/WEB SHA;
- пользовательские ссылки на кабинет должны использовать внешний TLS endpoint `https://de.funti.cc:8446/web/`, а не внутренние порты 8210/8220 и не корень домена без порта.

## Завершённый этап

На production развернут application release SHA `01fe8547e9038c098b4f4ea22f449622d4b774ea`.

WEB-контур поддерживает календарь на день, неделю и месяц, полные XLSX-выгрузки, карточки клиенток, мобильный logout и устойчивый возврат из Telegram при входе.

Telegram-редактирование существующей услуги без переименования принято в production: цена и длительность сохраняются после подтверждения, даже если модель передаёт только одно из эквивалентных полей имени.

Production verification: deploy `DEPLOY_OK=true`, checkout/runtime SHA совпадают, backup создан; живая Telegram-приёмка `update_service` пройдена.

WEB-002 реализовал подтверждённое owner-scoped web-редактирование каталога с atomic replace и verified readback. Последующие изменения упростили форму мастера и добавили редактируемые предустановленные разделы прайса.

## Зафиксированное продуктовое решение

Создан нормативный документ `docs/product/product-principles.md`.

Ключевые решения:

- продукт не позиционируется и не проектируется как CRM;
- главные области — «Календарь», «Мой прайс», «Клиентки»;
- «Услуги» в пользовательском интерфейсе заменяются на «Мой прайс»;
- «категория» становится «разделом прайса»;
- базовая форма содержит только название, раздел, цену, обычное время и необязательное описание;
- сложные типы цены, дополнения, варианты и правила времени раскрываются только при необходимости;
- время процедуры является ориентиром и может зависеть от клиентки и состояния ногтей;
- Нэйли может предлагать лучшие практики, но не меняет данные без подтверждения мастера;
- перенос реального прайса не блокирует дальнейшую разработку и может быть выполнен после ответов мастера.

## Текущая задача

PR #164 — editable presets для разделов прайса и фиксация продуктовой философии.

Границы текущего PR:

- предустановленные, но редактируемые разделы прайса;
- нормативный product-principles document;
- обязательная ссылка на него из `AGENTS.md` и текущего контекста;
- без изменения backend-модели каталога;
- без реализации дополнений, вариантов и импорта реального прайса.

## Следующий приоритет

1. Завершить PR #164: review → CI → merge → production release при наличии runtime-изменений.
2. Следующим продуктовым slice переименовать пользовательский раздел «Услуги» в «Мой прайс» и привести тексты формы к нормативной терминологии.
3. Перестроить список в визуальный прайс с группировкой по разделам и простыми карточками.
4. Затем перейти к конструктору записи «основная процедура + дополнения» без ожидания ответов мастера.
5. После получения ответов собрать и проверить первый реальный прайс отдельно.

## Точка продолжения

```text
production_application_release_sha=01fe8547e9038c098b4f4ea22f449622d4b774ea
active_pr=164
active_branch=fix/web-service-category-presets
product_source_of_truth=docs/product/product-principles.md
public_master_portal=https://de.funti.cc:8446/web/
release_contract=PR candidate optional before merge; merged main uses one atomic deploy.sh flow, no separate finalize
next=finish PR 164, then implement UX slice My Price terminology and grouped price-list presentation
```
