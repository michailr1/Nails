# Nails — текущий контекст

Дата фиксации: **10 августа 2026 года**.

Перед работой прочитать `AGENTS.md`, этот файл, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. Production state не предполагать.

## Фактическое production-состояние

Последний свежий VPS preflight перед candidate #297 подтвердил:

```text
repository=michailr1/Nails
production host=de.funti.cc
public master portal=https://de.funti.cc:8446/web/
production repo=/opt/nails/repo
production branch: main
backend env=/opt/nails/.env
internal API=http://127.0.0.1:8210
production_sha=3e4eb842895f458a591ff30208d206a10af472e9
running_api_sha=3e4eb842895f458a591ff30208d206a10af472e9
running_web_sha=3e4eb842895f458a591ff30208d206a10af472e9
running_client_bot_sha=3e4eb842895f458a591ff30208d206a10af472e9
alembic_head=0025
api_health=200
api_readiness=200
public_web=200
client_bot_singleton=true
legacy_client_bot_active=inactive
client_forward_state=active
last_verified_deploy=DEPLOY_OK=true
```

Fresh preflight также подтвердил clean production checkout, неизменённый production env/runtime/DB во время candidate попыток и health/readiness/web `200`.

## Release contract

- Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и merge.
- VPS-агент только исполняет утверждённые candidate/deploy/diagnostic runbook'и.
- PR candidate проверяется из exact `origin/pr/<number>` без изменения production checkout.
- Exact candidate SHA всегда берётся из fresh GitHub PR/preflight; его нельзя пиновать внутри этого же изменяемого контекстного файла, иначе любой context commit сам делает такой SHA устаревшим.
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

## Последние production-релизы

### #285 — реальный onboarding submit timezone

PR #293 / release `7da1d0725a4cb34d713eab1e9866f6030ffbdb10` исправил второй скрытый submit formatter в фактической цепочке `ContactAwareOnboardingBot -> OnboardingDraftPlatformBot`.

Production acceptance доказал: draft и submit показывают один owner-local момент; raw UTC в клиентское сообщение не попадает. #285 закрыт completed.

### #277 slice 1 — короткий booking-flow

PR #294 / release `38621112d3276763c3909804df49d524cdcf945f`:

- после выбора процедуры клиентка сразу переходит к дате даже при наличии addons;
- отдельный addon-screen больше не mandatory gate;
- дополнения остаются доступными из итоговой сводки;
- `Как в прошлый раз` открывает owner-local date picker и сохраняет прошлый состав.

Production acceptance зелёный.

### #277 slice 2 — «Мои записи»

PR #295 / release `fb0ab3f14c69b72d5ff7210b93e1b8bfbcb7c484`:

- переиспользован существующий owner-isolated `GET /api/v1/client/requests`, без новой history-модели;
- показываются только будущие `pending`/`approved`;
- `rejected`, `cancelled` и прошлые записи скрыты из основного списка;
- сортировка по фактическому времени визита;
- время отображается в timezone мастера;
- pending сохраняет кнопку отмены, approved — нет.

Production read-only diagnostic подтвердил exact release, owner-local filter/sort и runtime invariants.

### #277 slice 3 — optional request note

PR #296 / release `3e4eb842895f458a591ff30208d206a10af472e9`, Alembic `0025`:

- одна необязательная заметка клиентки к конкретной заявке, максимум 300 символов;
- note хранится в draft и snapshot'ится в `BookingRequest` при submit;
- note не меняет service/addons/slot/price/duration;
- client submit/list projections остаются note-free;
- trusted master projection и WEB BFF получают note;
- audit остаётся без свободного текста;
- durable master-forward включает note, оставаясь plain-text без `parse_mode`;
- кабинет экранирует note через `escapeHtml`;
- migration `0025` добавляет nullable `VARCHAR(300)` в `client_booking_drafts` и `booking_requests`.

Candidate acceptance отдельно доказал, что `11:00+03:00` и `08:00Z` — один absolute instant: различие ISO-представления не является изменением выбранного слота.

Fresh production preflight перед #297 подтверждает, что этот release уже является текущим production baseline и Alembic head=`0025`.

## Активный slice — #277 catalog sections/readability

Активная ветка и PR:

```text
active_issue=277
active_pr=297
active_branch=feat/catalog-sections-readability-277
base=3e4eb842895f458a591ff30208d206a10af472e9
candidate_head=resolve_from_fresh_GitHub_PR_preflight
candidate_migration=none
expected_alembic_head=0025
```

Цель — presentation-only улучшение `Мой прайс`:

- существующие category groups становятся native collapsible `<details>/<summary>`;
- по умолчанию sections collapsed;
- section с active editor открывается автоматически;
- существующие `serviceSummaryCard` / `serviceEditorCard` и save/remove paths переиспользуются;
- fixed/range/per-unit/on-request цены показываются читаемо;
- отсутствующая цена не превращается в `0 ₽`, а показывается как `цена уточняется`;
- base duration, addon extra time и master buffer-after показываются человекочитаемо;
- русские count labels: `1 позиция`, `2 позиции`, `N позиций`;
- mobile <=760px stack и long-name wrap;
- только существующие design tokens, без literal hex/rgb colors;
- DB/API/catalog-domain/schema не меняются.

Repository regression:
`backend/tests/test_web_catalog_readability_277.py` фиксирует полный source-level presentation contract и должен запускаться в exact candidate worktree вместо временных synthetic JS/browser harnesses.

История candidate #297:

1. `e46b5a6...` — fail closed из-за временного harness с пустым `serviceCatalogDraft`;
2. `e46b5a6...` — fail closed из-за временного harness, ошибочно привязавшего `catalogGroups()` к `this`; actual source `this` не использует;
3. `99f8a5b...` — fail closed ДО startup из-за устаревшего `docs/context/current.md` (`fb0ab3.../0024` против fresh production `3e4eb842.../0025`);
4. production context обновлён через PR. Для обновлённого контекста CI #1422, Agent responsibility #1333 и Production infrastructure contract #221 зелёные. Следующий candidate использует fresh exact PR head и baseline `3e4eb842.../0025`.

Ни один предыдущий fail-closed не доказал product-source defect. Production во всех попытках остался неизменным и healthy.

## Что остаётся после catalog readability slice

Issue #277 не закрывать автоматически. Остаток acceptance:

1. реальная Telegram/мобильная 360px приёмка коротких кнопок и section flow;
2. overlap при master correction должен оставаться виден до сохранения — authoritative `create_booking()` validation уже переиспользуется, но acceptance нужно зафиксировать по факту;
3. затем вернуться к #280 cabinet reload/render ownership и к #284/#282 effective schedule UX.

## Точка продолжения

```text
production_sha=3e4eb842895f458a591ff30208d206a10af472e9
alembic_head=0025
active_issue=277
active_pr=297
active_branch=feat/catalog-sections-readability-277
candidate_head=resolve_from_fresh_GitHub_PR_preflight
client_bot_singleton=true
client_forward_state=active
release_flow=exact PR-head candidate -> GitHub ready -> merge exact head -> exact main deploy.sh
next=exact candidate acceptance using repository regression -> merge/deploy if green
```
