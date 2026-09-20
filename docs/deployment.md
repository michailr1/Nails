# Развёртывание Nails на VPS

Дата актуализации: **20 сентября 2026 года**.

## 1. Production location

```text
host: de.funti.cc
repo: /opt/nails/repo
env: /opt/nails/.env
backups: /opt/nails/backups
API loopback: 127.0.0.1:8210
master web: https://de.funti.cc:8446/web/
```

Exact running SHA **не фиксируется как вечная константа в этом документе**. Перед candidate/deploy всегда выполнять fresh GitHub + VPS preflight.

Последний подтверждённый production release в актуальном контексте: `9b9c4829dfc6595441421a9d3c8fc2f6a53120af`. В `main` после него есть `4ab4e6f...`, который требует отдельного deploy confirmation.

## 2. Runtime topology

Штатный Compose содержит:

```text
nails-db
nails-api
nails-client-bot
nails-web
```

Master Telegram работает отдельным Hermes gateway/profile.

Legacy host `nails-client-bot.service` не должен одновременно работать с Compose client bot на том же token.

## 3. Feature flags client runtime

Допустимы только два состояния:

```text
CLIENT_API_ENABLED=false
CLIENT_BOT_ENABLED=false
```

или

```text
CLIENT_API_ENABLED=true
CLIENT_BOT_ENABLED=true
```

Mixed state запрещён.

При enabled обязательны:

- отдельный `CLIENT_INTERNAL_API_KEY`;
- `CLIENT_TELEGRAM_BOT_TOKEN`;
- client token отличается от master Telegram token;
- один runtime на token.

## 4. Production environment

`/opt/nails/.env`:

- вне repository;
- root-owned;
- secret values не печатать;
- placeholders запрещены;
- любые изменения только отдельной контролируемой операцией.

## 5. Production deploy

Единственный постоянный entrypoint:

```bash
cd /opt/nails/repo
./ops/deploy/deploy.sh <exact-main-sha>
```

Перед deploy:

1. exact SHA существует в `origin/main`;
2. CI exact SHA зелёный;
3. required candidate/acceptance завершён;
4. working tree clean;
5. production preflight не расходится с ожидаемым состоянием.

Deploy сам обязан создать backup перед mutating steps.

## 6. Candidate

Pre-merge candidate должен быть изолирован от production:

- отдельный Compose project;
- отдельные ports/networks/volume;
- без production env/DB;
- client bot для candidate не должен конкурировать с production token;
- cleanup удаляет candidate resources.

Для candidate использовать нормативный isolated adapter/runbook из `ops/deploy/candidate_deploy.sh`, а не production deploy semantics.

## 7. Rollback

Rollback — deploy предыдущего exact SHA штатным production entrypoint с release mode `rollback`. Не выполнять ручное редактирование source/.env/DB как «быстрый фикс».

## 8. Runtime acceptance

Минимум проверять:

- API health/readiness;
- public web;
- running web SHA;
- running client bot SHA при enabled;
- singleton client bot;
- legacy runtime inactive;
- Alembic head;
- production DB volume unchanged outside expected migration;
- backup path;
- no manual SQL/source/env mutation.

## 9. Security

- PostgreSQL не публикует внешний host port;
- API bind loopback;
- containers non-root/read-only/cap-drop where defined;
- client runtime не имеет direct DB access;
- master/client tokens и internal keys разделены;
- secrets не попадают в logs/issues/PRs.

## 10. Текущий migration head

В GitHub `main` на дату документа:

```text
Alembic: 0025
```

Перед deploy сверять фактический head заново.
