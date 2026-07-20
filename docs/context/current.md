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
production application release SHA: c128a3844243255f4ce9ab4ac8075a7e2249c61b
runtime API SHA: c128a3844243255f4ce9ab4ac8075a7e2249c61b
runtime WEB SHA: c128a3844243255f4ce9ab4ac8075a7e2249c61b
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
loopback web: http://127.0.0.1:8220/web/
health: /health
readiness: /ready
timezone: Europe/Moscow
Hermes plugins: nails-onboarding, nails-scheduling
finalization digest timer: enabled, active
last verified backup: /opt/nails/backups/nails-before-deploy-20260720T064428Z.sql.gz
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

На production развернут application release SHA `c128a3844243255f4ce9ab4ac8075a7e2249c61b`.

WEB-контур теперь поддерживает:

- календарь на день, неделю и месяц;
- экспорт выбранного периода и всего календаря;
- экспорт всех клиенток со всеми полями;
- мобильный выход из сессии.

Итоги дня теперь:

- выбирают только записи, начавшиеся в указанную локальную дату;
- не подтягивают старые незавершённые записи из прошлых дней;
- показывают дату в заголовке;
- допускают короткие ответы по номеру или имени;
- ведут к сводке с общей подтверждённой суммой перед записью изменений.

Production verification: backup валиден, миграции `0013 (head)`, API `/health` и `/ready` — 200, web — 200, gateway active, digest service установлен, timer enabled/active.

## Следующий приоритет

1. Провести живую WEB-приёмку календаря: день / неделя / месяц, logout и выгрузки.
2. Провести следующую безопасную проверку итогов дня на реальных новых записях без ручного запуска Telegram-дайджеста.
3. После acceptance перейти к первому web write-slice — редактированию каталога услуг с переиспользованием существующей backend-валидации и подтверждённой batch-модели.
4. Затем добавить редактирование графика и записей.

## Точка продолжения

```text
production_application_release_sha=c128a3844243255f4ce9ab4ac8075a7e2249c61b
public_master_portal=https://de.funti.cc:8446/web/
release_contract=PR candidate optional before merge; merged main uses one atomic deploy.sh flow, no separate finalize
next=live web acceptance, then web service catalog editor
```
