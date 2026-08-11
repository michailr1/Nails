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
production_sha=ae01054ebec67e8925680ac521c919be112e6c0e
running_api_sha=ae01054ebec67e8925680ac521c919be112e6c0e
running_web_sha=ae01054ebec67e8925680ac521c919be112e6c0e
running_client_bot_sha=ae01054ebec67e8925680ac521c919be112e6c0e
alembic_head=0025
api_health=200
api_readiness=200
public_web=200
client_bot_singleton=true
legacy_client_bot_active=inactive
client_forward_state=active
last_verified_deploy=DEPLOY_OK=true
```

Последний backup перед release #297: `/opt/nails/backups/nails-before-deploy-20260810T233634Z.sql.gz`, verified=true. Post-deploy acceptance также подтвердил clean working tree, unchanged production env, отсутствие manual SQL/runtime changes и exact runtime SHA во всех production-компонентах.

## Release contract

- Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и merge.
- VPS-агент только исполняет утверждённые candidate/deploy/diagnostic runbook'и.
- PR candidate проверяется из exact `origin/pr/<number>` без изменения production checkout.
- Exact candidate SHA всегда берётся из fresh GitHub PR/preflight; его нельзя self-pin'ить внутри этого же изменяемого контекстного файла.
- Production deploy выполняется только постоянным `ops/deploy/deploy.sh <exact-SHA>`.
- отдельного finalize entrypoint нет.
- Никакого ручного SQL, source edit, `.env` edit, runtime repair или rollback на VPS.
- Успех считается доказанным только по фактическому GitHub/VPS-отчёту.
- Если fresh production preflight противоречит `docs/context/current.md`, candidate acceptance обязан fail closed до обновления контекста через PR -> CI.

Operational anchors:

- Hermes plugins: `nails-onboarding`, `nails-scheduling`;
- роли только `master`, `admin`, `client`;
- один живой Telegram-тест за раз;
- отдельный deterministic client bot `@smartnails_bot`;
- один client-bot runtime на token;
- имя помощницы — «Нэйли»;
- Нэйли — личная помощница мастера, а не CRM;
- основной пользовательский раздел каталога — «Мой прайс».

## Последние #277 production-срезы

### PR #294 — короткий booking-flow

Release `38621112d3276763c3909804df49d524cdcf945f`:

- service -> date напрямую;
- addon screen не mandatory gate;
- `Как в прошлый раз` сохраняет состав и открывает owner-local date picker.

### PR #295 — «Мои записи»

Release `fb0ab3f14c69b72d5ff7210b93e1b8bfbcb7c484`:

- только будущие `pending`/`approved`;
- owner-local время;
- appointment-time sort;
- pending cancellable, approved без cancel.

### PR #296 — optional request note

Release `3e4eb842895f458a591ff30208d206a10af472e9`, Alembic `0025`:

- note до 300 символов в draft/request snapshot;
- note не меняет composition/slot/price/duration;
- client projections note-free;
- trusted master/API/BFF и durable master-forward получают note;
- audit без свободного текста;
- Telegram forward plain text, link preview disabled;
- cabinet note escaped.

### PR #297 — catalog sections/readability

Current production release `ae01054ebec67e8925680ac521c919be112e6c0e`:

- native collapsible `<details>/<summary>` sections в `Мой прайс`;
- sections collapsed by default, active editor section auto-open;
- existing editor/save/remove paths reused;
- fixed/range/per-unit/on-request prices readable; missing price != `0 ₽`;
- base/addon/buffer duration readable;
- Russian position counts;
- mobile <=760px stack, long-name wrap;
- existing design tokens/dark theme preserved;
- API/domain/DB schema unchanged;
- exact repository readability contract passed 10/10 in candidate and production checkout.

## Активный slice — #277 master-correction overlap acceptance

```text
active_issue=277
active_pr=298
active_branch=test/request-overlap-277
base=ae01054ebec67e8925680ac521c919be112e6c0e
candidate_head=resolve_from_fresh_GitHub_PR_preflight
candidate_migration=none
expected_alembic_head=0025
```

Цель — не менять product/domain код, а закрыть последний code-level acceptance gap #277 точным regression:

- клиентская заявка на base service 60 минут сама помещается до следующей записи;
- мастер перед подтверждением добавляет addon `+50 мин`;
- authoritative `create_booking()` должен вернуть `booking_overlap` до persistence;
- request остаётся `pending`, без `booking_id` и без mutation исходных service/addons/time;
- tentative create-new client не должен протечь после failed approval;
- в БД не появляется вторая booking;
- cabinet показывает явный `booking_overlap` текст, оставляет dialog открытым и refresh'ит slots.

PR #298 содержит только regression + этот context refresh. Product API/schema/model/migration/domain/frontend code не меняется.

CI history #298:

1. initial head `2b1ea1f...` — backend test упал только из-за invalid test fixture: addon был создан с `duration_minutes=0`, нарушая общий DB constraint `duration_minutes > 0`;
2. fixture исправлена на valid positive duration; addon business-time в сценарии по-прежнему определяется `extra_minutes=50`;
3. head до context refresh `439af8d...` прошёл backend test suite; exact candidate должен определяться только после этого context commit и нового CI.

## Что остаётся после overlap slice

После зелёного PR #298 и production evidence в #277 останется только **реальная 360px Telegram/mobile приёмка** клиентского booking flow:

- разделы вместо плоского списка;
- не более ~6 кнопок на страницу раздела;
- короткие button labels не обрезаются;
- price/time читаются в message text;
- repeat-last виден при подходящем визите;
- без addons можно отправить заявку;
- optional note не создаёт mandatory step.

Это реальный UI acceptance, его нельзя честно заменить source-level тестом; потребуется один живой Telegram прогон с пользовательским участием. До этой точки все остальные #277 acceptance-пункты должны быть закрыты автоматизированными evidence.

## Точка продолжения

```text
production_sha=ae01054ebec67e8925680ac521c919be112e6c0e
alembic_head=0025
active_issue=277
active_pr=298
active_branch=test/request-overlap-277
candidate_head=resolve_from_fresh_GitHub_PR_preflight
client_bot_singleton=true
client_forward_state=active
release_flow=exact PR-head candidate -> GitHub ready -> merge exact head -> exact main deploy.sh
next=new CI after context refresh -> isolated candidate acceptance of overlap regression -> merge/deploy if green -> one real Telegram 360px acceptance
```
