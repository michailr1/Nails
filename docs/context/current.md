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
production_sha=65d59acc9e9ecf791fd928e102da671b76ab1a3d
running_api_sha=65d59acc9e9ecf791fd928e102da671b76ab1a3d
running_web_sha=65d59acc9e9ecf791fd928e102da671b76ab1a3d
running_client_bot_sha=65d59acc9e9ecf791fd928e102da671b76ab1a3d
alembic_head=0025
api_health=200
api_readiness=200
public_web=200
client_bot_singleton=true
legacy_client_bot_active=inactive
client_forward_state=active
working_tree_clean=true
production_env_unchanged=true
DEPLOY_OK=true
```

Последний backup: `/opt/nails/backups/nails-before-deploy-20260811T110226Z.sql.gz`, verified=true.

Release `65d59acc...` — PR #299, client category presentation: в `Записаться` основные намерения идут первыми, raw `Дополнительно` скрыт за понятным `Снятие и другие услуги`; в прайсе — `Дополнительные услуги`. Catalog/API/domain/DB не менялись.

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

## Активная задача — #300

Issue: **Wire usual working hours into slot suggestions; replace the 14-day per-date editor**.

```text
active_issue=300
active_branch=feat/usual-working-hours-300
base=65d59acc9e9ecf791fd928e102da671b76ab1a3d
candidate_head=resolve_from_fresh_GitHub_PR_preflight
candidate_migration=none
expected_alembic_head=0025
```

Факты до правки:

- `MasterPreferences.default_work_intervals` уже существует;
- `DefaultWorkInterval` — окно без дня недели;
- `save_default_work_hours` уже сохраняет и audit'ит настройку;
- API onboarding `/preferences/default-work-hours` уже существует;
- assistant уже знает об обычных рабочих часах;
- slot engines до #300 эту настройку не читали;
- WEB показывал отдельный 14-дневный список `WORKING_SCHEDULE_DAYS = 14`.

Решение #300:

1. Один источник обычных часов остаётся `MasterPreferences.default_work_intervals`; новых таблиц/миграций нет.
2. Единый порядок suggestion windows:
   - date-specific `availability_intervals`;
   - обычные `default_work_intervals`;
   - fallback `10:00–23:00`.
3. ADR-006 не меняется: эти окна ограничивают только подсказки. Explicit booking по-прежнему блокируется только whole-day day-off и overlap.
4. И master free-slots, и client booking-draft slots используют один resolver.
5. В кабинете обычные часы задаются одним действием в `Настройки` под нейтральной иконкой мастера, рядом с отображением timezone.
6. Legacy 14-day editor `web-working-schedule.js/.css` удаляется, а не дублируется новой настройкой.
7. Исключения по конкретным датам остаются предметом Календаря / #284; weekly template и сменные графики не вводятся.

Ключевой regression:

- мастер одним PUT сохраняет `10:00–21:00`;
- связанная клиентка через booking draft получает первый слот `10:00`, последний для 60-минутной услуги `20:00`;
- date override `12:00–18:00` имеет приоритет;
- без обоих источников сохраняется fallback `10:00–23:00`.

## #277

#277 остаётся отдельной live-acceptance задачей после production #299. #300 не меняет client catalog presentation.

## Точка продолжения

```text
production_sha=65d59acc9e9ecf791fd928e102da671b76ab1a3d
alembic_head=0025
active_issue=300
active_branch=feat/usual-working-hours-300
candidate_head=resolve_from_fresh_GitHub_PR_preflight
client_bot_singleton=true
client_forward_state=active
next=finish tests/review -> PR #300 -> CI -> isolated candidate -> exact merge/deploy
```
