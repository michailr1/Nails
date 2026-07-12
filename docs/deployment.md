# Развёртывание Nails на VPS

Дата актуализации: **13 июля 2026 года**.

## 1. Production target

Nails развёрнут только на VPS:

```text
de.funti.cc
```

Репозиторий:

```text
/opt/nails/repo
```

Production environment:

```text
/opt/nails/.env
```

Текущий production commit:

```text
cca0109ea8c716fdf03d97c34a1c0f06bfb5fc50
```

## 2. Текущее состояние

```text
nails-api — running, healthy
nails-db  — running, healthy
```

API:

```text
127.0.0.1:8210
```

Alembic:

```text
0001 (head)
```

Проверенные ответы:

```json
{"status":"ok"}
```

```json
{"status":"ready"}
```

## 3. Docker runtime

На VPS используется Ubuntu Docker package:

```text
docker.io 29.1.3-0ubuntu3~24.04.2
```

Compose установлен совместимым Ubuntu package:

```text
docker-compose-v2 2.40.3+ds1-0ubuntu1~24.04.1
```

CLI plugin:

```text
/usr/libexec/docker/cli-plugins/docker-compose
```

Используется команда:

```bash
docker compose
```

Официальный Docker APT repository на сервер не добавлялся. `docker.io` не заменялся на `docker-ce`.

## 4. Production `.env`

Файл создаётся вне репозитория:

```text
/opt/nails/.env
```

Требования:

- owner `root:root`;
- mode `600`;
- не выводить содержимое в отчёты;
- не копировать значения из `.env.example` без замены placeholder;
- не коммитить;
- не публиковать полный `DATABASE_URL`.

Обязательные группы настроек:

- `APP_TIMEZONE`;
- PostgreSQL bootstrap role;
- PostgreSQL application role;
- `DATABASE_URL` application role;
- loopback bind и API port.

Production timezone:

```text
Europe/Berlin
```

## 5. PostgreSQL roles

### Bootstrap

```text
nails_admin
```

Используется только при первичной инициализации volume.

### Application

```text
nails_app
```

Booking API подключается только этой ролью.

Проверенные ограничения:

```text
SUPERUSER=0
CREATEDB=0
CREATEROLE=0
REPLICATION=0
```

Контрольный вывод:

```text
0|0|0|0
```

## 6. Compose topology

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

- `nails-db` is connected only to `nails-internal`;
- PostgreSQL has no published host port;
- `nails-api` connects to both networks;
- API is published only on loopback;
- other Docker projects and networks must not be changed.

## 7. API container hardening

Expected settings:

```text
user=nails
readonly=true
CapDrop=["ALL"]
no-new-privileges:true
```

These settings must not be weakened directly on VPS. Any change goes through GitHub, PR and CI.

## 8. Standard deployment procedure

Before deployment:

1. Confirm `hostname -f = de.funti.cc`.
2. Check that `/opt/nails/repo` working tree is clean.
3. Record current Nails and unrelated container status.
4. Verify exact expected commit.
5. Back up PostgreSQL before a data-changing migration when production contains business data.

Update source:

```bash
cd /opt/nails/repo
git fetch origin
git checkout main
git pull --ff-only origin main
```

Validate:

```bash
docker compose \
  --env-file /opt/nails/.env \
  config --quiet
```

Deploy:

```bash
docker compose \
  --env-file /opt/nails/.env \
  up -d --build --wait --wait-timeout 180
```

Do not use `down --volumes` during ordinary deployment.

## 9. Verification

Container status:

```bash
docker compose \
  --env-file /opt/nails/.env \
  ps
```

Health:

```bash
curl -fsS http://127.0.0.1:8210/health
curl -fsS http://127.0.0.1:8210/ready
```

Migrations:

```bash
docker compose \
  --env-file /opt/nails/.env \
  exec -T nails-api alembic current

docker compose \
  --env-file /opt/nails/.env \
  exec -T nails-api alembic heads
```

Repeated migration safety:

```bash
docker compose \
  --env-file /opt/nails/.env \
  exec -T nails-api alembic upgrade head
```

Published ports:

```bash
docker compose \
  --env-file /opt/nails/.env \
  port nails-api 8000

docker port nails-db 2>/dev/null || true
```

PostgreSQL output must be empty.

API DB identity must be:

```text
nails_app
```

## 10. Persistence test completed

A synthetic user row was created through `nails_app`, both Nails containers were restarted, and the row remained present. After the test, the synthetic row was deleted and absence was verified.

This confirms volume persistence across container restart. It does **not** replace backup or disaster recovery testing.

## 11. Existing unrelated services

The VPS also runs Amnezia containers:

```text
amnezia-awg2
amnezia-dns
amnezia-xray
```

They must not be restarted, reconfigured or removed by Nails deployment.

Forbidden general cleanup commands without a separate approved task:

```text
docker system prune
docker volume prune
docker network prune
apt upgrade
apt full-upgrade
apt dist-upgrade
systemctl restart docker
```

## 12. Deployment responsibility

Code and documentation are changed in GitHub by the main development workflow.

The VPS agent:

- deploys a specified commit from `main`;
- runs migrations and runtime checks;
- does not edit tracked files;
- does not commit or push;
- stops and reports exact diagnostics when deployment fails.

## 13. Known deployment blockers resolved

### Missing Compose CLI

The VPS initially had `docker.io` without Compose. The compatible Ubuntu package `docker-compose-v2` was installed without replacing or restarting Docker Engine.

### Internal-only network blocked host access

The first CI topology placed API only on an internal network. Container health succeeded, but host loopback access failed. The final topology keeps DB internal and gives API a separate `nails-edge` network while binding to `127.0.0.1`.

### Excessive database privileges

The initial design could have made the API use the PostgreSQL bootstrap user. The final deployment separates `nails_admin` and restricted `nails_app` and verifies the effective user in CI and production.

## 14. Before pilot

Still required:

- automated backup schedule;
- off-host or off-disk backup copy;
- restore into a separate database;
- documented restore result;
- monitoring of backup failures;
- end-to-end onboarding and scheduling tests;
- removal of synthetic data.
