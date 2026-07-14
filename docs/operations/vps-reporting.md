# Concise VPS reporting contract

Status: **mandatory for new Nails deployment and diagnostic prompts**.

The full command output remains on the production server in a root-only log when a runbook provides a log path. It is not pasted into the working chat by default.

## Successful run

The VPS agent returns only:

- the runbook success marker;
- HEAD before and after;
- backup and diagnostic log paths;
- schema/Alembic before and after;
- changed/unchanged container markers;
- backend health/readiness;
- plugin and gateway markers;
- business-data non-change markers;
- rollback status.

Do not return routine output from:

- `git merge` file statistics;
- Docker build layers;
- package downloads and installation;
- successful repeated checks;
- complete service journals.

## Failed run

The VPS agent returns only:

- `DEPLOYMENT_FAILED=true`;
- runbook and failed stage/line;
- the concise safe error;
- HEAD and affected service state;
- backup and full-log paths;
- the complete concise `ROLLBACK_*` block;
- up to 60 relevant lines from a failed build or service log when the runbook itself emits them.

The VPS agent never summarizes away a failed rollback marker, but also never pastes unrelated successful build output.

## Main-agent prompts

Every new VPS prompt must say:

```text
Верни только итоговые markers runbook. Не вставляй git diff/stat, Docker build layers,
pip output или полный journal. При ошибке верни DEPLOYMENT_FAILED, безопасную ошибку,
пути логов и полный ROLLBACK_* блок.
```

This reporting rule reduces chat/context growth without reducing auditability: full logs stay on the server at the paths emitted by the runbook.
