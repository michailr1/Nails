# Nails — текущий контекст

Дата фиксации: **20 сентября 2026 года**.

Перед работой читать `AGENTS.md`, этот файл, product/engineering principles и принятые ADR. Обязательный engineering source: `docs/operations/engineering-principles.md`. GitHub и production всегда проверять фактически: tracked-документы не заменяют preflight. **Production state не предполагать.**

production branch: main

## Source of truth

- GitHub `main` на момент актуализации: `4ab4e6f80adefad80d03bf5b484d051b974738e1`.
- Последний подтверждённый production deploy: `9b9c4829dfc6595441421a9d3c8fc2f6a53120af`.
- `4ab4e6f...` **не считать production**, пока VPS не подтвердит deploy/running SHA.
- Alembic head в текущем `main`: `0025`.

Exact refs для новых решений всё равно разрешать заново.

## Архитектурные anchors

- master bot: Hermes profile `nails`;
- client bot: отдельный deterministic runtime;
- один client platform bot на всех мастеров;
- `start_token -> owner_user_id` только server-side;
- multi-binding включён;
- публичного каталога мастеров нет;
- `master_public_profile.display_name` обязателен для активной ссылки;
- `public_contact` только opt-in;
- numeric master Telegram ID клиентке не раскрывается;
- pending client request не резервирует слот;
- master approve повторно проверяет slot/day-off;
- client runtime не ходит в БД напрямую;
- client API и bot feature flags включаются/выключаются только вместе;
- один client-bot runtime на token; legacy host runtime должен быть inactive;
- роли только `master`, `admin`, `client`;
- один живой Telegram-тест за раз.

## Что уже не является активной разработкой

ADR-004/client contour, ADR-009 binding и client runtime **реализованы**. Не возвращать obsolete single-master server-config `CLIENT_OWNER_TELEGRAM_USER_ID` и не планировать bot-per-master.

Старые issues #171 и #248 должны рассматриваться как завершённые по фактическому коду/production history, а не как roadmap.

## Текущий UI/release контекст

Последний merge в `main` — #326 / #325:

- mobile bottom nav на узком viewport переведена на стабильные 4 равные колонки;
- invite buttons больше не образуют тупик при незаполненном public profile;
- при необходимости открывается «Как вас увидят клиентки»;
- после сохранения profile экран «Клиентки» обновляется;
- CI exact head был зелёным перед merge.

Нужен отдельный production deploy/acceptance `4ab4e6f...`.

Issue #323 остаётся открытым до фактической mobile acceptance request cards + confirm dialog + profile placement.

## Release contract

- основной ChatGPT: архитектура, код, тесты, GitHub, CI, review, merge;
- VPS-агент: candidate/production deploy, runtime acceptance, diagnostics, rollback;
- pre-merge candidate — только изолированным candidate path;
- production deploy — только штатным `ops/deploy/deploy.sh <exact-main-sha>`;
- backup перед mutating deploy;
- никаких manual source/.env/SQL/runtime fixes;
- при расхождении refs/runtime — fail closed.

## Реально открытые направления

- #323 mobile UI acceptance;
- #316 branch protection;
- #268 остаточный cabinet UX debt;
- #252 web render/script-order tech debt;
- #223 future self-service master onboarding.

## Точка продолжения

```text
origin_main_at_doc_refresh=4ab4e6f80adefad80d03bf5b484d051b974738e1
last_confirmed_production=9b9c4829dfc6595441421a9d3c8fc2f6a53120af
alembic_head=0025
client_contour=implemented
client_binding=multi-master
client_runtime=permanent-compose-runtime
client_bot_singleton_required=true
next=refresh preflight -> deploy/accept 4ab4e6f if still main -> continue only real open issues
```
