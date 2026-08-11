# Nails — текущий контекст

Дата фиксации: **11 августа 2026 года**.

Перед работой прочитать `AGENTS.md`, этот файл, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. Production state не предполагать.

## Фактическое production-состояние

Последний production deploy и read-only post-deploy acceptance подтвердили:

```text
repository=michailr1/Nails
production host=de.funti.cc
public master portal=https://de.funti.cc:8446/web/
production repo=/opt/nails/repo
production branch=main
backend env=/opt/nails/.env
production_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
prev_sha=65d59acc9e9ecf791fd928e102da671b76ab1a3d
checkout_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
origin_main_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
running_api_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
running_web_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
running_client_bot_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
alembic_head=0025
api_health=200
api_readiness=200
public_web=200
client_runtime_enabled=true
client_bot_singleton=true
legacy_client_bot_active=inactive
working_tree_clean=true
production_env_unchanged=true
manual_sql_executed=false
manual_runtime_changes=false
manual_source_changes=false
POST_DEPLOY_OK=true
```

Последний backup: `/opt/nails/backups/nails-before-deploy-20260811T141445Z.sql.gz`.

Release `64ad3cf...` — PR #301 / issue #300. Обычные рабочие часы `MasterPreferences.default_work_intervals` подключены к slot suggestions единым resolver'ом: date-specific `availability_intervals` → обычные часы → ADR-006 fallback `10:00–23:00`. Master free-slots и client booking-draft slots используют один resolver. ADR-006 сохранён: положительные окна остаются подсказками; hard gates — whole-day day-off и overlap. В кабинете обычные часы задаются одним действием в настройках; legacy 14-day editor удалён. Новых таблиц и миграций нет.

## Release contract

- Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и merge.
- VPS-агент только исполняет candidate/deploy/diagnostic runbook'и.
- Exact candidate SHA берётся из fresh GitHub PR/preflight и не self-pin'ится в этом файле.
- Candidate проверяется из exact PR head без изменения production checkout.
- Production deploy — только штатный `ops/deploy/deploy.sh <exact-main-SHA>` / нормативный `NAILS_RELEASE_REF=origin/main` entrypoint.
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

## Завершённая задача #300

Issue: **Wire usual working hours into slot suggestions; replace the 14-day per-date editor**.

Фактический release:

```text
issue=300
pr=301
release_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
candidate_acceptance=true
selected_suite_passed=true
adr006_preserved=true
candidate_cleanup_ok=true
production_invariants=true
production_deploy=true
expected_alembic_head=0025
```

Реализовано и принято:

1. Один источник обычных часов — `MasterPreferences.default_work_intervals`; новых таблиц/миграций нет.
2. Единый порядок suggestion windows:
   - date-specific `availability_intervals`;
   - обычные `default_work_intervals`;
   - fallback `10:00–23:00`.
3. ADR-006 не менялся: positive windows ограничивают подсказки; explicit booking блокируется whole-day day-off и overlap.
4. Master free-slots и client booking-draft slots используют один resolver.
5. Обычные часы задаются одним действием в настройках мастера рядом с timezone.
6. Legacy `web-working-schedule.js/.css` удалён.
7. Исключения по конкретным датам остаются предметом Календаря / #284; weekly template и сменные графики не вводятся.
8. Exact isolated candidate acceptance прошёл на `64ad3cf...`; затем тот же exact SHA fast-forward merged в `main` и штатно задеплоен.

Ключевой regression доказал:

- мастер сохраняет `10:00–21:00`;
- связанная клиентка получает первый слот `10:00`, последний для 60-минутной услуги `20:00`;
- date override `12:00–18:00` имеет приоритет;
- без обоих источников сохраняется fallback `10:00–23:00`.

## Следующая активная задача — #284

Issue: **Master cannot see or change what limits client slots; unblock schedule editor candidate**.

После #300 часть #284 закрыта архитектурно: источник обычных часов и `availability_intervals` не дублируются, а являются двумя слоями одного resolver'а; обычные часы теперь реально влияют на клиентские подсказки. Оставшийся scope #284 нужно сверить по fresh issue/code перед правками.

Предварительно остаётся:

- day-specific exception UX в Календаре: особые часы/выходной для конкретной даты;
- отображение эффективных ограничений выбранного дня: окно, выходной, занятость существующими записями;
- согласованный ответ Нэйли о фактическом расписании/ограничениях, а не только о default hours;
- end-to-end live acceptance от изменения конкретного дня до клиентских слотов;
- ADR-006 не менять: сужение positive suggestion window поверх существующей записи разрешено, сама запись не меняется; whole-day day-off при конфликте остаётся hard gate.

Перед реализацией #284 обязательно перечитать fresh issue и текущий `main`: старые пункты про candidate `91739e10` могут быть историческими и не должны исполняться автоматически.

## Точка продолжения

```text
production_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
checkout_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
origin_main_sha=64ad3cf9e7a4525e3188f185fbe8bcdfbc2fd396
alembic_head=0025
completed_issue=300
completed_pr=301
active_issue=284
active_branch=resolve_after_fresh_preflight
candidate_head=resolve_from_fresh_GitHub_PR_preflight
client_bot_singleton=true
legacy_client_bot_active=inactive
next=fresh #284/code preflight -> define remaining scope -> branch -> tests -> PR -> CI -> isolated candidate -> exact merge/deploy
```
