# Развёртывание Nails на VPS

Дата актуализации: **13 июля 2026 года**.

## 1. Production target

Работать только на:

```text
de.funti.cc
```

Paths:

```text
/opt/nails/repo
/opt/nails/.env
```

Production до NAILS-002B:

```text
commit cca0109ea8c716fdf03d97c34a1c0f06bfb5fc50
migration 0001 (head)
API 127.0.0.1:8210
```

После merge PR #11 deployment должен использовать отдельно переданный точный main commit и привести Alembic к `0002 (head)`.

## 2. Docker runtime

```text
docker.io 29.1.3-0ubuntu3~24.04.2
docker-compose-v2 2.40.3+ds1-0ubuntu1~24.04.1
```

Compose plugin:

```text
/usr/libexec/docker/cli-plugins/docker-compose
```

Использовать `docker compose`. Не добавлять Docker APT repository и не заменять `docker.io` на `docker-ce`.

## 3. Production environment

```text
/opt/nails/.env
```

Requirements:

- `root:root`;
- mode `600`;
- outside repository;
- contents never printed;
- full `DATABASE_URL` never included in reports;
- backup before modification.

Required settings:

```text
APP_TIMEZONE
INTERNAL_API_KEY
POSTGRES_DB
POSTGRES_ADMIN_USER
POSTGRES_ADMIN_PASSWORD
APP_DB_USER
APP_DB_PASSWORD
DATABASE_URL
NAILS_API_BIND
NAILS_API_PORT
```

### `INTERNAL_API_KEY`

NAILS-002B requires a separately generated secret with at least 32 characters.

Rules:

- generate on production host with cryptographically secure randomness;
- store only in `/opt/nails/.env` and later in the restricted Hermes domain tool configuration;
- never put it in GitHub, logs, command history or model prompt;
- do not use `.env.example` value in production;
- rotate through a separate controlled procedure.

Until NAILS-002C, Hermes does not receive this key.

Production timezone remains:

```text
Europe/Berlin
```

## 4. Services and isolation

```text
nails-api
nails-db
```

Volume:

```text
nails-postgres-data
```

Networks:

```text
nails-edge
nails-internal
```

Topology:

```text
127.0.0.1:8210
      ↓
  nails-api
   ├── nails-edge
   └── nails-internal
             ↓
          nails-db
```

- DB only on `nails-internal`;
- PostgreSQL has no host port;
- API bind only on loopback;
- other Docker projects remain untouched.

## 5. PostgreSQL identities

### Bootstrap

```text
nails_admin
```

Only for initialization/controlled administration.

### Application

```text
nails_app
```

Expected flags:

```text
SUPERUSER=0
CREATEDB=0
CREATEROLE=0
REPLICATION=0
```

API current user must be `nails_app`.

## 6. API container hardening

Expected:

```text
user=nails
readonly=true
CapDrop=["ALL"]
no-new-privileges:true
```

Do not weaken on VPS. Changes go through GitHub and CI.

## 7. Pre-deployment checklist

1. Confirm `hostname -f = de.funti.cc`.
2. Confirm clean `/opt/nails/repo`.
3. Record exact current commit and container state.
4. Record Amnezia IDs and `StartedAt`.
5. Verify expected new main SHA.
6. Create PostgreSQL backup before migration.
7. Verify backup integrity.
8. Back up `/opt/nails/.env` with mode `600`.
9. Add secure `INTERNAL_API_KEY` only if absent.
10. Never edit tracked files.

## 8. Source update

```bash
cd /opt/nails/repo
git fetch origin
git checkout main
git pull --ff-only origin main
```

Then verify exact SHA and clean tree.

## 9. Compose validation and deployment

```bash
docker compose \
  --env-file /opt/nails/.env \
  config --quiet
```

```bash
docker compose \
  --env-file /opt/nails/.env \
  up -d --build --wait --wait-timeout 180
```

Never use during ordinary deployment:

```text
docker compose down --volumes
docker system prune
docker volume prune
docker network prune
```

## 10. Infrastructure verification

```bash
docker compose --env-file /opt/nails/.env ps
curl -fsS http://127.0.0.1:8210/health
curl -fsS http://127.0.0.1:8210/ready
```

Migration:

```bash
docker compose --env-file /opt/nails/.env exec -T nails-api alembic current
docker compose --env-file /opt/nails/.env exec -T nails-api alembic heads
docker compose --env-file /opt/nails/.env exec -T nails-api alembic upgrade head
```

Expected after NAILS-002B:

```text
0002 (head)
```

Repeated upgrade must be clean.

Ports:

```bash
docker compose --env-file /opt/nails/.env port nails-api 8000
docker port nails-db 2>/dev/null || true
```

API must show `127.0.0.1:8210`; DB output must be empty.

## 11. NAILS-002B API verification

Use only a synthetic Telegram ID and synthetic business data.

Required tests:

1. Missing internal key → `401`.
2. Wrong internal key → `401`.
3. Unknown user → `403`.
4. Inactive user → `403`.
5. Active `admin` or `master` can start onboarding.
6. Save schedule draft; verify `effective_payload=null` before confirmation.
7. Confirm schedule; repeat confirmation; verify no duplicate confirmation audit.
8. Edit schedule; verify new draft revision and previous confirmed payload remains effective.
9. Pause onboarding.
10. Restart only `nails-api`.
11. Get state; verify paused state and drafts persisted.
12. Resume onboarding.
13. Verify confirmation order for services/buffers/bookings.
14. Verify unknown service reference rejected.
15. Complete all sections and repeat complete idempotently.
16. Verify audit does not contain full payload or contact values.
17. Delete all synthetic users, states, drafts and audit rows.

Do not add real Telegram IDs or real client information.

Detailed contract: [`onboarding-api.md`](onboarding-api.md).

## 12. Logs

Check both services after migration and tests:

```bash
docker compose --env-file /opt/nails/.env logs --tail 150 nails-api
docker compose --env-file /opt/nails/.env logs --tail 150 nails-db
```

No:

- traceback;
- migration error;
- authentication loop;
- repeated restart;
- secret or complete onboarding payload.

## 13. Rollback boundary

The VPS agent does not change code or migration files.

On deployment failure:

- stop testing;
- preserve diagnostics;
- do not edit tracked files;
- do not create ad-hoc SQL schema fixes;
- do not reset or delete the database volume;
- report exact commit, migration state, container status and logs.

A migration downgrade or data restore requires a separate approved recovery plan.

## 14. Unrelated services

Existing Amnezia containers:

```text
amnezia-awg2
amnezia-dns
amnezia-xray
```

They must keep the same IDs, `StartedAt` and running state. Do not restart Docker daemon, Amnezia, Hermes, Nginx/Traefik or other projects.

## 15. Responsibility split

Main development workflow:

- code;
- migrations;
- tests;
- CI;
- docs;
- PR and merge.

VPS agent:

- fetch exact main commit;
- backup;
- deploy;
- migrate;
- run synthetic production tests;
- clean synthetic data;
- report results.

VPS agent never edits tracked files, commits or pushes.

## 16. Before real-data pilot

Still required:

- Hermes restricted onboarding tool;
- production onboarding skill;
- materialization into working schedule/services/bookings;
- scheduling end-to-end flow;
- automated backup;
- off-host/off-disk copy;
- verified restore;
- test data cleanup and privacy checks.
