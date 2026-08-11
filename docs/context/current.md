# Nails — текущий контекст

Дата фиксации: **11 августа 2026 года**.

Перед работой прочитать `AGENTS.md`, этот файл, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. Production state не предполагать.

## Фактическое production-состояние

Последний production deploy и post-deploy acceptance подтвердили:

```text
repository=michailr1/Nails
production host=de.funti.cc
public master portal=https://de.funti.cc:8446/web/
production repo=/opt/nails/repo
production branch: main
backend env=/opt/nails/.env
internal API=http://127.0.0.1:8210
production_sha=ed983b1e529eb4f0ebb378fd104101dbe4737d22
running_api_sha=ed983b1e529eb4f0ebb378fd104101dbe4737d22
running_web_sha=ed983b1e529eb4f0ebb378fd104101dbe4737d22
running_client_bot_sha=ed983b1e529eb4f0ebb378fd104101dbe4737d22
alembic_head=0025
api_health=200
api_readiness=200
public_web=200
client_bot_singleton=true
legacy_client_bot_active=inactive
client_forward_state=active
last_verified_deploy=DEPLOY_OK=true
```

Последний backup: `/opt/nails/backups/nails-before-deploy-20260811T064412Z.sql.gz`, verified=true. Release #298 менял только tests/context; production acceptance подтвердил product/API/schema/models/migrations/domain/frontend unchanged, clean worktree и unchanged env.

## Release contract

- Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и merge.
- VPS-агент только исполняет утверждённые candidate/deploy/diagnostic runbook'и.
- PR candidate проверяется из exact `origin/pr/<number>` без изменения production checkout.
- Exact candidate SHA всегда берётся из fresh GitHub PR/preflight; его нельзя self-pin'ить внутри этого же изменяемого контекстного файла.
- Production deploy выполняется только постоянным `ops/deploy/deploy.sh <exact-SHA>`.
- отдельного finalize entrypoint нет.
- Никакого ручного SQL, source edit, `.env` edit, runtime repair или rollback на VPS.
- Если fresh production preflight противоречит `docs/context/current.md`, candidate acceptance обязан fail closed до context update через PR -> CI.

Operational anchors:

- Hermes plugins: `nails-onboarding`, `nails-scheduling`;
- роли только `master`, `admin`, `client`;
- один живой Telegram-тест за раз;
- отдельный deterministic client bot `@smartnails_bot`;
- один client-bot runtime на token;
- имя помощницы — «Нэйли»;
- Нэйли — личная помощница мастера, а не CRM;
- основной пользовательский раздел каталога — «Мой прайс».

## #277 — завершённые production-срезы

- PR #294: короткий booking flow, addons больше не mandatory gate, repeat-last -> owner-local date picker.
- PR #295: `Мои записи`, только будущие pending/approved, owner-local time.
- PR #296: optional request note до 300 символов, trusted master surfaces, note-free client/audit boundaries, Alembic `0025`.
- PR #297: сворачиваемые readable sections в кабинете мастера; production catalog contract 10/10.
- PR #298: regression доказал master-added addon overlap before save; product code unchanged.

## Live Telegram acceptance — найденный дефект

Issue #277 был автоматически закрыт merge'ом #298, но reopen'нут, потому что обязательная реальная 360px Telegram-приёмка нашла UX-дефект на production `ed983b1...`.

Скриншоты показали:

- в `Записаться` первым top-level пунктом идёт сырой catalog category `Дополнительно`;
- в `Прайс` тот же сырой технический label показывается рядом с основными клиентскими разделами;
- клиентке непонятно, что означает «Дополнительно» и почему это главный/первый выбор.

Root cause: `client_bot_catalog_sections.py` использует raw `category` и first-seen catalog order. В booking фильтр `kind=base` корректный, но некоторые самостоятельные base services имеют category `Дополнительно`, поэтому технический label становится top-level intent.

## Активный fix — client category presentation

```text
active_issue=277
active_branch=fix/client-category-presentation-277
base=ed983b1e529eb4f0ebb378fd104101dbe4737d22
candidate_head=resolve_from_fresh_GitHub_PR_preflight
candidate_migration=none
expected_alembic_head=0025
```

Fix presentation-only:

- raw catalog category/data не меняются;
- callbacks продолжают адресовать raw category/index;
- `Записаться`: primary client intents идут первыми; raw `Дополнительно` показывается последним как `Снятие и другие услуги`;
- `Прайс`: `Маникюр`, `Педикюр`, `Дизайн`, `Парафинотерапия`, затем raw `Дополнительно` как `Дополнительные услуги`;
- unknown categories сохраняются и не теряются;
- catalog/domain/API/DB schema unchanged.

Regression `backend/tests/test_client_category_presentation_277.py` фиксирует live-bug order/labels и доказывает отсутствие mutation исходных catalog categories.

## Что остаётся

После fix/deploy повторить реальную Telegram 360px проверку:

- `Записаться` — понятные primary sections, без сырого `Дополнительно` в начале;
- раздел — <=6 коротких buttons/page;
- price/time читаются в message text;
- no-addons submit работает;
- optional note не mandatory;
- repeat-last при подходящем визите;
- `Прайс` — понятные client-facing section labels/order.

#277 закрывать только после этого повторного live acceptance.

## Точка продолжения

```text
production_sha=ed983b1e529eb4f0ebb378fd104101dbe4737d22
alembic_head=0025
active_issue=277
active_branch=fix/client-category-presentation-277
candidate_head=resolve_from_fresh_GitHub_PR_preflight
client_bot_singleton=true
client_forward_state=active
release_flow=exact PR-head candidate -> GitHub ready -> merge exact head -> exact main deploy.sh
next=PR + CI for client category presentation -> isolated candidate -> deploy -> repeat live Telegram 360px acceptance
```
