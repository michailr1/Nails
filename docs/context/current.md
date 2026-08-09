# Nails — текущий контекст

Дата фиксации: **9 августа 2026 года**.

Перед работой прочитать `AGENTS.md`, этот файл, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. Production state не предполагать.

## Фактическое production-состояние

```text
repository=michailr1/Nails
production host=de.funti.cc
public master portal=https://de.funti.cc:8446/web/
production repo=/opt/nails/repo
production branch: main
backend env=/opt/nails/.env
internal API=http://127.0.0.1:8210
production_sha=fb0ab3f14c69b72d5ff7210b93e1b8bfbcb7c484
running_api_sha=fb0ab3f14c69b72d5ff7210b93e1b8bfbcb7c484
running_web_sha=fb0ab3f14c69b72d5ff7210b93e1b8bfbcb7c484
running_client_bot_sha=fb0ab3f14c69b72d5ff7210b93e1b8bfbcb7c484
alembic_head=0024
api_health=200
api_readiness=200
public_web=200
client_bot_singleton=true
legacy_client_bot_active=inactive
client_forward_state=active
last_verified_deploy=DEPLOY_OK=true
```

Последняя production-проверка также подтвердила валидный backup, чистый working tree, отсутствие ручного SQL/runtime mutations и exact release SHA во всех runtime-компонентах.

## Release contract

- Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и merge.
- VPS-агент только исполняет утверждённые candidate/deploy/diagnostic runbook'и.
- PR candidate проверяется из exact `origin/pr/<number>` без изменения production checkout.
- Production deploy выполняется только постоянным `ops/deploy/deploy.sh <exact-SHA>`.
- отдельного finalize entrypoint нет.
- Никакого ручного SQL, source edit, `.env` edit, runtime repair или rollback на VPS.
- Успех считается доказанным только по фактическому GitHub/VPS-отчёту.

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

Production read-only diagnostic подтверждает exact release, owner-local filter/sort и runtime invariants.

## Активный slice — #277 optional request note

Активная ветка:

```text
active_issue=277
active_branch=feat/client-request-note-277
base=fb0ab3f14c69b72d5ff7210b93e1b8bfbcb7c484
candidate_migration=0025
```

Цель: одна необязательная заметка клиентки к конкретной заявке, не переписка.

Зафиксированные инварианты:

- заметка существует в draft и snapshot'ится в `BookingRequest` при submit;
- максимум 300 символов, blank нормализуется в `None`;
- свободный текст никогда не становится аргументом `create_booking()`, состава, слота, цены или длительности;
- note отсутствует в client submit/list/cancel projections и client lifecycle notifications;
- note присутствует только в trusted master request projection, карточке кабинета и durable master-forward;
- audit остаётся структурным и не содержит note/text;
- master Telegram forward остаётся plain text без `parse_mode`; существующий sender уже ставит `disable_web_page_preview=true`;
- кабинет рендерит note только через `escapeHtml`;
- master-forward создаётся в той же transaction, что BookingRequest, поэтому note и уведомление не расходятся;
- migration `0025` expand-only: nullable `VARCHAR(300)` в `client_booking_drafts` и `booking_requests`.

Client UX не получает новый обязательный шаг: после time selection текущая summary/send остаётся рабочей; рядом предлагается необязательная `📝 Заметка мастеру`.

## Что остаётся после note slice

Issue #277 не закрывать автоматически. Проверить остаток acceptance:

1. сворачиваемые разделы `Мой прайс` в кабинете и единый читаемый формат цены/времени;
2. реальная Telegram 360px приёмка коротких кнопок/section flow;
3. overlap при master correction должен оставаться виден до сохранения — текущий путь уже переиспользует authoritative `create_booking()` validation, но acceptance нужно фиксировать по факту;
4. затем вернуться к #280 cabinet reload/render ownership и к #284/#282 effective schedule UX.

## Точка продолжения

```text
production_sha=fb0ab3f14c69b72d5ff7210b93e1b8bfbcb7c484
alembic_head=0024
active_issue=277
active_branch=feat/client-request-note-277
candidate_migration=0025
client_bot_singleton=true
client_forward_state=active
release_flow=exact PR-head candidate -> GitHub merge -> exact main deploy.sh
next=finish note regressions -> draft PR -> CI/self-review -> isolated candidate -> merge/deploy if green
```
