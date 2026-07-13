# Фактическое состояние проекта

Дата актуализации: **13 июля 2026 года**.

Документ разделяет состояние Git checkout, backend runtime, Hermes runtime и следующие этапы.

## 1. Сводка

| Область | Состояние |
|---|---|
| Бизнес-правила MVP | базово согласованы, NAILS-001 ещё открыт |
| Hermes Telegram Gateway | production, работает |
| Профиль `nails` | production, restricted plugin установлен |
| Backend foundation | NAILS-002A production |
| Onboarding API | NAILS-002B production |
| Hermes → Onboarding API | NAILS-002C установлен и проверен synthetic smoke |
| Реальный Telegram two-user test | остался последний acceptance step |
| Production migration | `0002 (head)` |
| Scheduling happy path | не реализован |
| Backup/restore-test | автоматизация и restore-test не реализованы |
| Пилот с мастером | не начат |

## 2. Production versions

Host:

```text
de.funti.cc
```

Repository checkout:

```text
/opt/nails/repo
HEAD = ae761e5042e2af4685df7bdb1de9485e96bdac74
working tree = clean
```

Commit `ae761e…` включает runtime plugin commit:

```text
d8264266256f6fc2c53b6eebd3b9bb6bbc722f7c
```

Последующие три commit после `d826426…` меняли только документацию.

Backend containers не пересобирались при NAILS-002C и продолжают проверенный NAILS-002B runtime:

```text
backend release code = 40b25ff5fe519eda8602d0eeac7d06a1b191138d
Alembic = 0002 (head)
```

## 3. Backend production

Containers:

```text
nails-api — running, healthy
nails-db  — running, healthy
```

API:

```text
127.0.0.1:8210
GET /health → {"status":"ok"}
GET /ready  → {"status":"ready"}
```

PostgreSQL:

- host port отсутствует;
- API current user: `nails_app`;
- role flags: `0|0|0|0` для SUPERUSER/CREATEDB/CREATEROLE/REPLICATION;
- `nails_admin` используется только для bootstrap and controlled administration.

API container:

- user `nails`;
- read-only root filesystem;
- `CapDrop=["ALL"]`;
- `no-new-privileges:true`;
- bind only on loopback.

## 4. NAILS-002B baseline

Onboarding API supports:

```text
POST /api/v1/onboarding/start
GET  /api/v1/onboarding
PUT  /api/v1/onboarding/sections/{section}
POST /api/v1/onboarding/sections/{section}/confirm
POST /api/v1/onboarding/pause
POST /api/v1/onboarding/resume
POST /api/v1/onboarding/complete
```

Sections:

```text
schedule
services
buffers
bookings
```

Verified in production:

- active user and role checks;
- draft/confirmed separation;
- revision tracking;
- ordered confirmations;
- downstream invalidation;
- idempotent confirmation/completion;
- pause/resume after API restart;
- safe audit metadata;
- synthetic cleanup `0|0|0`.

Deployment record: [`deployments/2026-07-13-nails-002b.md`](deployments/2026-07-13-nails-002b.md).

## 5. NAILS-002C production installation

Plugin source:

```text
/opt/nails/repo/hermes/plugins/nails_onboarding
```

Installed to:

```text
/root/.hermes/profiles/nails/plugins/nails_onboarding
```

Plugin:

```text
name = nails-onboarding
version = 0.1.0
status = enabled
```

Source and target file hashes matched before activation.

Profile backup:

```text
/root/.hermes/profiles/nails/backups/nails-002c-20260713T092318Z
```

Backup mode:

```text
700 root:root
```

Profile environment:

- `NAILS_INTERNAL_API_KEY` synchronized from backend runtime setting;
- values matched;
- length check passed;
- value was not printed;
- `.env` remains `600 root:root`.

SOUL source/target hash matched.

Full record: [`deployments/2026-07-13-nails-002c.md`](deployments/2026-07-13-nails-002c.md).

## 6. Hermes production

Profile:

```text
nails
```

Enabled Telegram tools exactly:

```text
clarify
image_gen
nails_onboarding
skills
tts
vision
```

Forbidden tools remain disabled:

```text
terminal
file
code_execution
web
browser
memory
session_search
delegation
cronjob
computer_use
context_engine
todo
kanban
MCP
GitHub
SSH
deploy tools
```

Built-in memory/user profile remain disabled.

`skills.write_approval=true`.

Gateway restart:

```text
old PID = 991980
new PID = 1677495
state = active (running)
```

Recent logs contained no plugin import error, manifest error, missing environment error, polling conflict, traceback or secret leak.

## 7. Trusted identity and plugin boundary

Tool:

```text
nails_onboarding
```

Model-visible arguments:

```text
action
section
payload
```

Identity does not appear in tool schema.

Runtime identity source:

```python
get_session_env("HERMES_SESSION_PLATFORM", "")
get_session_env("HERMES_SESSION_USER_ID", "")
```

Properties:

- fail closed unless platform is `telegram`;
- Telegram ID cannot be supplied by the model;
- URL is fixed to `http://127.0.0.1:8210`;
- headers and request ID are generated inside runtime;
- generic HTTP is not exposed;
- backend performs its own active user and role checks;
- backend `401` and `403` map to the same safe response.

## 8. NAILS-002C production smoke

Result:

```text
NAILS_002C_PLUGIN_SMOKE_OK
```

Verified:

- non-Telegram context fails closed;
- spoofed `telegram_user_id` argument rejected as `invalid_arguments` before network access;
- unknown and inactive users receive identical `access_denied`;
- two synthetic users receive distinct onboarding state and drafts;
- plugin calls production backend through loopback;
- synthetic cleanup result: `0|0|0`;
- backend health/readiness remained green;
- Docker daemon was not restarted;
- backend containers were not rebuilt;
- Amnezia IDs and `StartedAt` did not change;
- default Hermes profile, bot token and allowlist were not changed.

## 9. Production users

Two existing allowlisted Telegram users are provisioned in backend roles without publishing their IDs:

- one `admin`;
- one `master`.

Telegram allowlist itself was not changed during deployment.

## 10. Remaining NAILS-002C acceptance

Issue #5 remains open only for a short real Telegram test:

1. account A starts onboarding through the Telegram bot;
2. account B starts independently and cannot see A state;
3. account A pauses onboarding;
4. only `hermes-gateway-nails` is restarted;
5. account A resumes and receives its own preserved state;
6. a text request to access another user does not change trusted identity;
7. logs are checked for secrets and disclosure.

After these checks NAILS-002C can be marked production-complete and issue #5 closed.

## 11. What is not implemented yet

- production onboarding conversation skill;
- materialization of confirmed onboarding blocks into working services/schedule/bookings;
- availability search;
- booking create/transfer/cancel;
- automatic backup schedule;
- off-host/off-disk backup copy;
- verified restore;
- Google Calendar.

## 12. Next steps

1. Complete two-account Telegram acceptance for NAILS-002C.
2. Close issue #5.
3. Implement NAILS-002D production onboarding skill.
4. Implement NAILS-002E materialization and scheduling happy path.
5. Implement NAILS-002F automated backup and verified restore.
6. Run full synthetic end-to-end test and cleanup.
7. Start limited pilot only after all safety gates pass.

## 13. Change process

- code, migrations, tests and docs change through GitHub;
- CI is mandatory;
- VPS agent deploys exact `main` commits;
- VPS agent does not edit tracked files and does not push;
- production errors return to development as diagnostics.
