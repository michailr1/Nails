# Nails — текущий контекст

Дата фиксации: **9 августа 2026 года**.

Перед работой прочитать `AGENTS.md`, этот файл, `docs/product/product-principles.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. Production state не предполагать.

## Фактическое production-состояние

```text
repository=michailr1/Nails
production host: de.funti.cc
public master portal: https://de.funti.cc:8446/web/
production repo: /opt/nails/repo
production branch: main
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
production_sha=cc28b9976cdbd640db61da6e9ebbcbdaaf41d506
running_api_sha=cc28b9976cdbd640db61da6e9ebbcbdaaf41d506
running_web_sha=cc28b9976cdbd640db61da6e9ebbcbdaaf41d506
running_client_bot_sha=cc28b9976cdbd640db61da6e9ebbcbdaaf41d506
alembic_head=0023
api_health=200
api_readiness=200
public_web=200
client_bot_singleton=true
legacy_client_bot_active=inactive
current_master_timezone_stored=null
current_master_timezone_effective=Europe/Moscow
last_verified_backup=/opt/nails/backups/nails-before-deploy-20260807T162338Z.sql.gz
last_verified_deploy=DEPLOY_OK=true
```

Production working tree clean. Existing users keep `users.timezone=NULL`; effective timezone falls back to configured `Europe/Moscow`. Production `.env` was not changed by the timezone rollout.

Operational runtime facts retained as mandatory context anchors:

- Hermes plugins: `nails-onboarding`, `nails-scheduling`;
- один живой Telegram-тест за раз;
- роли только `master`, `admin`, `client`;
- имя помощника — «Нэйли»;
- Нэйли — личная помощница мастера, а не CRM;
- основной пользовательский раздел каталога — «Мой прайс».

## Release contract

- Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и merge.
- VPS-агент только исполняет утверждённые candidate/deploy/diagnostic runbook'и.
- PR candidate проверяется из exact `origin/pr/<number>` без изменения production checkout.
- Production deploy выполняется только постоянным `ops/deploy/deploy.sh <exact-SHA>`.
- отдельного finalize entrypoint нет.
- Успех считается доказанным только по фактическому tool/VPS-отчёту.

## Последний завершённый большой этап

PR #287 добавил per-master timezone:

- nullable `users.timezone` и миграцию `0023`;
- owner-aware timezone для scheduling, calendar, statistics, exports, digest, client bot и web;
- IANA validation и preferences API;
- spring-DST guard для nonexistent local wall times и дедупликацию UTC slot instants;
- owner timezone в client notification outbox;
- удаление frontend-зависимости от `APP_TIMEZONE`.

Exact candidate `9330f835b9ea3b109245466fc53cacabcf7ab891` был принят, production работает на `cc28b9976cdbd640db61da6e9ebbcbdaaf41d506`.

## Активный production-дефект #285

Реальная Telegram-приёмка после deploy выявила пропущенный путь:

- сводка черновика показывает `16.08 в 14:45`;
- после отправки той же заявки сообщение `✅ Заявка отправлена` показывает `16.08 в 11:45`.

Причина подтверждена в `backend/app/client_bot_booking_flow.py`: submit-ответ API сериализуется в UTC, а клиентский бот форматировал `result.starts_at` без `astimezone(master timezone)`.

Issue #285 переоткрыт. Активная ветка:

```text
fix/client-submit-timezone-285
base=cc28b9976cdbd640db61da6e9ebbcbdaaf41d506
```

Критерий: slot/draft/submit/cabinet/notifications должны показывать один owner-local момент; отдельный regression для Europe/Moscow и America/New_York, без фиксированного `+03`.

## Следующий блокер #290

После hotfix #285 реализовать issue #290:

1. мастер может до подтверждения pending-заявки изменить процедуру, дополнения и время, используя существующий booking/catalog/overlap domain;
2. Booking создаётся только после явного финального подтверждения и fresh validation;
3. клиентка получает финальные подтверждённые значения;
4. при новой клиентской заявке Нэйли немедленно уведомляет мастера в trusted Telegram-контуре;
5. уведомление идемпотентно, owner-scoped и retryable; сбой доставки не теряет заявку.

Не создавать второй booking engine или новое хранилище без доказанной необходимости. Сначала инвентаризировать существующие booking-edit, client-forward/outbox и trusted Telegram delivery механизмы.

## После критичных блокеров

Порядок:

1. #285 — исправить расхождение времени submit confirmation;
2. #290 — редактирование pending-заявки мастером + Telegram notification мастеру;
3. #277/#280 — упростить клиентский flow: меньше шагов, необязательные дополнения без навязанного экрана, читаемые разделы, «Как в прошлый раз», «Мои записи»;
4. #284/#282 — эффективный рабочий график и объяснение ограничений дня;
5. #286/#268 — account menu и оставшийся mobile cabinet UX;
6. #252 — убрать глобальные render overrides/script-order coupling.

## Точка продолжения

```text
production_sha=cc28b9976cdbd640db61da6e9ebbcbdaaf41d506
alembic_head=0023
active_issue=285
active_branch=fix/client-submit-timezone-285
next_issue=290
client_bot_singleton=true
current_master_timezone_effective=Europe/Moscow
release_flow=exact PR-head candidate -> same accepted release -> deploy.sh
next=finish #285 regression tests and CI, candidate acceptance, merge/deploy, then implement #290
```
