# Развёртывание Nails на VPS

Дата актуализации: **13 июля 2026 года**.

## 1. Production baseline

Host:

```text
de.funti.cc
```

Paths:

```text
/opt/nails/repo
/opt/nails/.env
/opt/nails/backups
```

Current production:

```text
commit: 40b25ff5fe519eda8602d0eeac7d06a1b191138d
Alembic: 0002 (head)
API: 127.0.0.1:8210
```

Latest verified deployment record:

[`deployments/2026-07-13-nails-002b.md`](deployments/2026-07-13-nails-002b.md)

## 2. Docker runtime

```text
docker.io 29.1.3-0ubuntu3~24.04.2
docker-compose-v2 2.40.3+ds1-0ubuntu1~24.04.1
```

Compose plugin:

```text
/usr/libexec/docker/cli-plugins/docker-compose
```

Use `docker compose`. Do not add Docker upstream repository or replace `docker.io` with `docker-ce` without a separate approved task.

## 3. Production environment

```text
/opt/nails/.env
```

Requirements:

- owner `root:root`;
- mode `600`;
- outside repository;
- never print contents;
- never report full `DATABASE_URL`;
- back up before modification;
- placeholders from `.env.example` are forbidden in production.

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

`INTERNAL_API_KEY`:

- generated with secure randomness;
- minimum 32 characters;
- stored only in production runtime configuration;
- never placed in GitHub, prompt, answer or logs;
- later shared only with the restricted Hermes onboarding tool;
- rotation requires a separate controlled deployment.

Production timezone:

```text
Europe/Berlin
```

## 4. Compose topology

Services:

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

Rules:

- `nails-db` only on `nails-internal`;
- PostgreSQL has no published host port;
- `nails-api` connects to edge and internal networks;
- API published only on loopback;
- unrelated Docker projects are not changed.

## 5. PostgreSQL identities

Bootstrap role:

```text
nails_admin
```

Used only for initialization and controlled administration.

Application role:

```text
nails_app
```

Expected attributes:

```text
SUPERUSER=0
CREATEDB=0
CREATEROLE=0
REPLICATION=0
```

API must connect as `nails_app`.

## 6. API container hardening

Expected:

```text
user=nails
readonly=true
CapDrop=["ALL"]
no-new-privileges:true
```

Hardening changes must go through GitHub, PR and CI.

## 7. Standard deployment procedure

### Pre-check

1. Confirm `hostname -f = de.funti.cc`.
2. Confirm clean `/opt/nails/repo`.
3. Record current commit and container state.
4. Record Docker daemon PID/start time.
5. Record Amnezia IDs and `StartedAt`.
6. Verify exact target commit.
7. Create and validate PostgreSQL backup before migration.
8. Back up `/opt/nails/.env` before changing it.
9. Never edit tracked files on VPS.

### Source update

```bash
cd /opt/nails/repo
git fetch origin
git checkout main
git pull --ff-only origin main
```

Verify exact target SHA and clean tree.

### Validate Compose

```bash
docker compose \
  --env-file /opt/nails/.env \
  config --quiet
```

### Deploy

```bash
docker compose \
  --env-file /opt/nails/.env \
  up -d --build --wait --wait-timeout 180
```

Forbidden during normal deployment:

```text
docker compose down --volumes
docker system prune
docker volume prune
docker network prune
systemctl restart docker
```

## 8. Verification

Containers:

```bash
docker compose --env-file /opt/nails/.env ps
```

Health:

```bash
curl -fsS http://127.0.0.1:8210/health
curl -fsS http://127.0.0.1:8210/ready
```

Migrations:

```bash
docker compose --env-file /opt/nails/.env exec -T nails-api alembic current
docker compose --env-file /opt/nails/.env exec -T nails-api alembic heads
docker compose --env-file /opt/nails/.env exec -T nails-api alembic upgrade head
```

Current expected revision:

```text
0002 (head)
```

Ports:

```bash
docker compose --env-file /opt/nails/.env port nails-api 8000
docker port nails-db 2>/dev/null || true
```

Expected:

- API only `127.0.0.1:8210`;
- DB output empty.

## 9. NAILS-002B verification baseline

Production has already verified:

- missing/wrong authentication → `401`;
- unknown/inactive synthetic user → `403`;
- active admin can start onboarding;
- invalid schedule → `422`;
- confirmation order enforcement;
- draft/effective separation;
- revision correction behavior;
- unknown service reference rejection;
- pause/restart/resume persistence;
- completion idempotency;
- safe audit counts and privacy;
- complete synthetic cleanup.

Future deployments touching onboarding must preserve these checks.

Detailed contract: [`onboarding-api.md`](onboarding-api.md).

## 10. NAILS-002C deployment boundary

The next release may add a restricted Hermes onboarding tool.

Mandatory properties:

- Telegram identity only from trusted gateway context;
- no model-visible Telegram ID argument;
- no generic HTTP, arbitrary URL or arbitrary headers;
- authentication setting hidden from model context;
- only onboarding domain operations exposed;
- no shell, file, SQL or other profile secrets;
- two-user owner isolation test;
- identity spoofing negative test;
- unknown/inactive user no-disclosure test;
- restart Hermes test;
- existing Telegram whitelist not broadened with universal tools.

## 11. Logs

```bash
docker compose --env-file /opt/nails/.env logs --tail 150 nails-api
docker compose --env-file /opt/nails/.env logs --tail 150 nails-db
```

No:

- traceback;
- migration error;
- repeated restart;
- authentication loop;
- secret;
- complete onboarding payload;
- personal data in diagnostic output.

## 12. Failure and rollback boundary

VPS agent does not change code or migrations.

On failure:

- stop further testing;
- preserve diagnostics;
- do not edit tracked files;
- do not apply ad-hoc SQL schema fixes;
- do not delete or reset the database volume;
- report exact commit, migration state, container status and logs.

Migration downgrade or data restore requires a separate approved recovery plan.

## 13. Unrelated services

Protected existing containers:

```text
amnezia-awg2
amnezia-dns
amnezia-xray
```

Do not restart or reconfigure Docker daemon, Amnezia, Hermes, Telegram gateway, Nginx/Traefik or other projects unless explicitly included in the task.

## 14. Responsibility split

Main development workflow:

- code;
- migrations;
- tests;
- CI;
- documentation;
- PR and merge.

VPS agent:

- backup;
- fetch exact `main` commit;
- deploy;
- migrate;
- run synthetic production checks;
- clean synthetic data;
- report results.

The VPS agent never edits tracked files, commits or pushes.

## 15. Before real-data pilot

Still required:

- restricted Hermes onboarding tool;
- production onboarding skill;
- materialization into working schedule/services/bookings;
- scheduling end-to-end flow;
- automated backups;
- off-host/off-disk copy;
- verified restore;
- final privacy and synthetic cleanup checks.
