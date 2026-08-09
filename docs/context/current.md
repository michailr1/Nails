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
production_sha=8852d09a17ddd9cb2563d1377e62d0e12d0a4aaa
running_api_sha=8852d09a17ddd9cb2563d1377e62d0e12d0a4aaa
running_web_sha=8852d09a17ddd9cb2563d1377e62d0e12d0a4aaa
running_client_bot_sha=8852d09a17ddd9cb2563d1377e62d0e12d0a4aaa
alembic_head=0023
api_health=200
api_readiness=200
public_web=200
client_bot_singleton=true
legacy_client_bot_active=inactive
client_forward_state=active
current_master_timezone_stored=null
current_master_timezone_effective=Europe/Moscow
last_verified_backup=/opt/nails/backups/nails-before-deploy-20260809T024639Z.sql.gz
last_verified_deploy=DEPLOY_OK=true
```

Production working tree clean. Production `.env` unchanged; no manual SQL/runtime mutations were used for the last release.

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

## Последний завершённый этап — #285

PR #291 / production `8852d09a17ddd9cb2563d1377e62d0e12d0a4aaa` закрыл оставшийся timezone-регресс клиентского submit-flow:

- draft `16.08 14:45` и `✅ Заявка отправлена` теперь показывают один owner-local момент;
- UTC submit serialization больше не превращается в пользовательские `11:45`;
- regression проверен для Europe/Moscow и America/New_York;
- production formatter acceptance `14:45 -> 14:45` прошёл;
- alembic остаётся `0023`.

Issue #285 закрыт как completed.

## Активный блокер #290

Production feedback выявил два связанных дефекта клиентского контура:

1. pending-заявка в кабинете мастера фактически read-only: только «подтвердить / не получится»;
2. новая заявка появляется в кабинете, но Нэйли не уведомляет мастера в Telegram.

Активная ветка:

```text
fix/pending-request-edit-notify-290
base=8852d09a17ddd9cb2563d1377e62d0e12d0a4aaa
candidate_migration=0024
```

Архитектурный срез:

- не создавать второй booking engine: финальное подтверждение использует существующий `create_booking()` и его fresh catalog/day-off/overlap validation;
- мастер до подтверждения может изменить основную процедуру, дополнения, время и при необходимости индивидуальную цену/длительность;
- браузер не конструирует timezone offset вручную: время выбирается из owner-aware server slots;
- request mutation происходит только после успешного создания Booking; ошибка/cancel оставляет pending request исходным;
- для уведомления мастера переиспользуется существующий durable `client-forward` claim/ack/retry runtime;
- migration `0024` добавляет forward `kind` и owner-scoped nullable `dedupe_key` с partial unique index;
- новый request и master-forward фиксируются одной DB transaction; idempotent resubmit не создаёт второй forward;
- delivery failure снимает claim и повторяется, не откатывая/не теряя уже committed BookingRequest;
- системный forward отображается как `📅 Новая заявка на запись`, а не как свободный текст клиентки.

## Candidate blocker, найденный 9 августа

Первый isolated candidate PR #292 остановился до проверки feature-кода:

```text
CANDIDATE_OK=false
reason=CANDIDATE_API_UNHEALTHY_DURING_UP
root_cause=deployment/postgres/init-app-user.sh tracked as Git mode 100644
```

Fresh Postgres initdb не исполнил bind-mounted shell script и не создал application role `nails_app`; API поэтому не мог аутентифицироваться к isolated candidate DB. Production checkout/runtime/DB остались неизменными, cleanup прошёл.

Исправление класса ошибки:

- `deployment/postgres/init-app-user.sh` должен быть tracked как `100755`;
- regression `test_candidate_deploy_env_isolation.py` теперь проверяет Git mode `100755` для init-script;
- VPS `chmod` запрещён: candidate обязан работать из exact Git tree без ручной коррекции permissions.

После нового exact-head CI candidate acceptance #292 повторяется с нуля.

Отдельно обнаружен latent debt: обычный `web-booking-edit.js` всё ещё строит `starts_at` с hardcoded `+03:00`. В #290 этот код не переиспользуется; исправить общий editor отдельным узким срезом после критичных блокеров либо раньше, если acceptance покажет влияние.

## После #290

Порядок:

1. #290 — редактирование pending-заявки + Telegram notification мастеру;
2. #277/#280 — упростить клиентский flow: убрать навязанный отдельный шаг дополнений, сократить путь записи, разделы прайса, «Как в прошлый раз», «Мои записи»;
3. #284/#282 — эффективный рабочий график и объяснение ограничений дня;
4. #286/#268 — account menu и оставшийся mobile cabinet UX;
5. hardcoded `+03:00` в общем booking editor — owner-aware edit contract;
6. #252 — убрать глобальные render overrides/script-order coupling.

## Точка продолжения

```text
production_sha=8852d09a17ddd9cb2563d1377e62d0e12d0a4aaa
alembic_head=0023
active_issue=290
active_branch=fix/pending-request-edit-notify-290
candidate_migration=0024
next_issue=277/280
client_bot_singleton=true
client_forward_state=active
current_master_timezone_effective=Europe/Moscow
release_flow=exact PR-head candidate -> GitHub merge -> exact main deploy.sh
next=verify init-app-user.sh Git mode 100755 on final head -> CI -> repeat isolated candidate #292
```
