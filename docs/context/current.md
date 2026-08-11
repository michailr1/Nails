# Nails — текущий контекст

Дата фиксации: **11 августа 2026 года**.

Перед работой прочитать `AGENTS.md`, этот файл, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. Production state не предполагать.

## Фактическое production-состояние

production branch: main. Последний production deploy и read-only post-deploy acceptance подтвердили:

```text
repository=michailr1/Nails
production host=de.funti.cc
public master portal=https://de.funti.cc:8446/web/
production repo=/opt/nails/repo
production branch=main
backend env=/opt/nails/.env
production_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
prev_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
checkout_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
origin_main_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
running_api_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
running_web_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
running_client_bot_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
client_runtime_enabled=true
client_bot_singleton=true
legacy_client_bot_active=inactive
alembic_head=0025
api_health=200
api_readiness=200
public_web=200
working_tree_clean=true
production_env_unchanged=true
manual_sql_executed=false
manual_runtime_changes=false
manual_source_changes=false
DEPLOY_OK=true
POST_DEPLOY_OK=true
```

Последний backup: `/opt/nails/backups/nails-before-deploy-20260811T192338Z.sql.gz`.

Release `8fec2cc1...` завершил #286: иконка мастера вынесена в угол, меню содержит «Профиль для клиенток», «Настройки», «Выйти», старые logout-контролы удалены, профиль мастера перенесён из раздела клиенток. Alembic остаётся `0025`.

## Текущая проблема — #304

Ручная приёмка на реальном iPhone выявила визуальный дефект release `8fec2cc1...`: модальные панели «Настройки» и «Как вас увидят клиентки» технически не переполняют viewport, но выглядят сломанно — слишком маленькие внешние поля, неясная композиция полей времени и слабая визуальная структура профиля.

Issue #304 исправляет только существующий web UI в месте причины:

- `backend/app/web_static/web-master-settings.css` — mobile shell, отступы и контролы;
- `backend/app/web_static/web-master-settings.js` — понятный пользовательский текст «Рабочий день», «Начало», «Конец»;
- `backend/app/web_static/web-public-profile-visible.js` остаётся на существующем API/markup-контракте и использует исправленный общий shell;
- backend, API, БД, timezone и scheduling semantics не меняются;
- regression должен фиксировать реальные мобильные gutters и отсутствие возврата к `calc(100vw - 20px/12px)`.

Активная ветка: `fix/304-mobile-master-settings-layout`.

## Release contract

- Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и merge.
- VPS-агент только исполняет candidate/deploy/diagnostic runbook'и.
- Exact candidate SHA берётся из fresh GitHub PR/preflight.
- Candidate не должен менять production checkout/runtime/DB; изолированный candidate entrypoint сверяется с актуальным operational контрактом и #303.
- Production deploy после merge — только штатный `ops/deploy/deploy.sh <exact-main-SHA>` / `NAILS_RELEASE_REF=origin/main`.
- отдельного finalize entrypoint нет.
- Никаких manual source/.env/SQL/DB/runtime fixes на VPS.
- При расхождении fresh preflight и target release context — fail closed.

Operational anchors:

- Hermes plugins: `nails-onboarding`, `nails-scheduling`;
- роли только `master`, `admin`, `client`;
- один живой Telegram-тест за раз;
- отдельный deterministic client bot `@smartnails_bot`;
- один client-bot runtime на token;
- имя помощницы — «Нэйли»;
- Нэйли — личная помощница мастера, а не CRM;
- основной пользовательский раздел каталога — «Мой прайс».

## После #304

Вернуться к fresh preflight оставшегося scope #284: исключения рабочего времени по конкретному дню и прозрачное отображение ограничений клиентских слотов. ADR-006 не менять.

## Точка продолжения

```text
production_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
checkout_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
origin_main_sha=8fec2cc1a6ebbebda0ac78c3cbd048903933a036
alembic_head=0025
active_issue=304
active_branch=fix/304-mobile-master-settings-layout
candidate_head=resolve_from_fresh_PR_preflight
client_bot_singleton=true
legacy_client_bot_active=inactive
next=finish #304 tests -> PR -> CI/review -> isolated candidate -> exact fast-forward merge -> deploy -> real iPhone acceptance
```
