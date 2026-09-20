# Nails deployment

Дата актуализации: **20 сентября 2026 года**.

Этот каталог содержит два разных operational path, которые нельзя смешивать:

- pre-merge isolated candidate: `ops/deploy/candidate_deploy.sh`;
- production release/rollback: `ops/deploy/deploy.sh`.

## 1. Production deploy — единственный постоянный production entrypoint

После merge:

```bash
cd /opt/nails/repo
NAILS_RELEASE_REF=origin/main bash ops/deploy/deploy.sh <exact-main-SHA>
```

Скрипт сам выполняет source/SHA preflight, release worktree, backup, build, migrations/runtime replacement, health/readiness/running-SHA checks и rollback при ошибке.

Rollback — тот же `deploy.sh` с предыдущим exact SHA и release mode `rollback`.

Никакого отдельного finalize entrypoint нет.

## 2. Pre-merge candidate

Для runtime-sensitive PR используется:

```bash
ops/deploy/candidate_deploy.sh
```

Candidate должен:

- строиться из exact открытого PR-head SHA;
- использовать отдельный Compose project;
- использовать отдельные ports/networks/volume;
- не использовать production DB/env;
- не менять production checkout;
- не пересоздавать production containers;
- не запускать client bot на production Telegram token;
- после acceptance удалять candidate resources.

`deploy.sh` не является candidate entrypoint.

## 3. Client runtime

Штатный production Compose включает `nails-client-bot`.

Release invariant:

- `CLIENT_API_ENABLED` и `CLIENT_BOT_ENABLED` только `false/false` либо `true/true`;
- client/master Telegram tokens различаются;
- client runtime один на token;
- legacy host `nails-client-bot.service` не должен конкурировать с Compose runtime;
- running client-bot SHA проверяется при release.

## 4. VPS-agent boundary

VPS-agent только исполняет exact runbook основного агента:

- diagnostic;
- candidate;
- main deploy;
- rollback;
- runtime acceptance.

Он не редактирует tracked files, не делает SQL/source/.env fixes и не меняет GitHub.

## 5. Production environment

Нормативные production paths и Hermes runtime детали находятся в:

- `docs/operations/production-infrastructure.md`;
- `docs/operations/hermes-plugin-runtime.md`;
- `docs/operations/agent-responsibilities.md`.

Hermes управляется через **root user-level systemd**; canonical profile config:

```text
/root/.hermes/profiles/nails/config.yaml
```

## 6. Исторические runbook'и

Одноразовые NAILS-002E* runbook'и больше не являются текущими entrypoint'ами. Их имена/маркеры ниже сохраняются только как исторические contract anchors и для старых deployment reports.

Старый generic execution template:

```text
ops/deploy/<APPROVED_RUNBOOK>.sh
```

Исторические E4/E5 anchors:

- `ops/deploy/nails-002e4-v3.sh`;
- `NAILS_002E4_V3_DEPLOYMENT_OK`;
- `ops/deploy/nails-002e5-date-availability.sh`;
- `NAILS_002E5_DEPLOYMENT_OK`.

`nails-002e4.sh` must **not** be executed again.

`nails-002e4-v2.sh` must **not** be executed again.

Исторические isolation markers, которые встречаются в старых reports:

```text
calendar_data_changed_by_deployment=false
manual_sql_executed=false
```

Наличие исторического имени скрипта в git history никогда не разрешает его выполнение. Для текущих релизов source of truth — `candidate_deploy.sh`, `deploy.sh`, AGENTS и свежий preflight.
