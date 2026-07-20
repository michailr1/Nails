# Nails — текущий контекст

Дата фиксации: **20 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

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

## Текущая задача

Issue #161 — WEB-002: первый web write-slice для каталога услуг.

Границы:

- переиспользовать существующие owner-scoped service catalog и atomic replace-catalog backend-механизмы;
- добавить раздел «Услуги» в текущий web shell без нового frontend framework;
- показывать активные и архивные позиции;
- перед одной атомарной записью показывать полный список создаваемых, изменяемых и архивируемых услуг;
- считать успехом только `verified=true` и затем перечитывать каталог;
- не включать график, записи, client/public каталог, photo import и multi-master.

## Следующий приоритет

1. Завершить WEB-002: code → tests → PR → CI → production release → живая web-приёмка.
2. Провести следующую безопасную проверку итогов дня на реальных новых записях без ручного запуска Telegram-дайджеста.
3. После WEB-002 перейти к web-редактированию графика, затем записей.

## Точка продолжения

```text
production_application_release_sha=01fe8547e9038c098b4f4ea22f449622d4b774ea
active_issue=161
active_branch=feat/web-service-catalog
public_master_portal=https://de.funti.cc:8446/web/
release_contract=PR candidate optional before merge; merged main uses one atomic deploy.sh flow, no separate finalize
next=finish WEB-002 service catalog editor, test, review, CI
```
