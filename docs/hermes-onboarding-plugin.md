# Restricted Hermes onboarding tool

Статус: реализовано в NAILS-002C, production deployment выполняется отдельно после merge.

## Назначение

Плагин соединяет Telegram-профиль Hermes `nails` с локальным onboarding API, не выдавая модели универсальный HTTP-клиент, identity fields или secrets.

Production install path:

```text
/root/.hermes/profiles/nails/plugins/nails_onboarding
```

Repository source:

```text
hermes/plugins/nails_onboarding
```

## Model-visible interface

Модель видит один tool:

```text
nails_onboarding
```

Toolset:

```text
nails_onboarding
```

Разрешённые аргументы:

```text
action
section
payload
```

Разрешённые actions:

```text
start
get_state
save_section
confirm_section
pause
resume
complete
```

Model-visible schema не содержит:

- Telegram user ID;
- chat ID;
- request ID;
- API key;
- URL;
- HTTP method;
- headers.

Unexpected arguments отклоняются до сетевого вызова.

## Trusted identity

Handler получает identity только из Hermes task-local context:

```python
get_session_env("HERMES_SESSION_PLATFORM", "")
get_session_env("HERMES_SESSION_USER_ID", "")
```

Tool fail closed, если:

- platform не `telegram`;
- user ID отсутствует;
- user ID не является положительным целым числом.

Не используются:

- текст сообщения;
- username;
- chat ID;
- parsing session key;
- Hermes SQLite;
- model arguments.

Backend повторно проверяет, что пользователь существует, active и имеет role `master` or `admin`.

## Backend boundary

Base URL жёстко задан:

```text
http://127.0.0.1:8210
```

Плагин не принимает URL или headers от модели.

Authentication setting:

```text
NAILS_INTERNAL_API_KEY
```

Он хранится в profile environment, помечен `secret: true` в manifest и не включается в tool result or logs.

## Request ID and retries

Каждый call получает runtime-generated request ID:

```text
nails-plugin-<uuid>
```

Плагин выполняет не более двух попыток с тем же request ID.

Retry разрешён только для:

- transport error;
- HTTP 502;
- HTTP 503;
- HTTP 504.

Не выполняется retry для validation, authorization and domain conflicts.

## Safe errors

- backend `401` and `403` map to identical `access_denied`;
- existence or inactive status пользователя не раскрываются;
- `404`, `409`, `422` return only safe code/details from backend;
- unknown backend body is not returned to the model;
- transport and 5xx errors become `service_unavailable`;
- secret and trusted user ID are not returned.

## SOUL behavior

После production installation Smart Nails может говорить:

- «черновик сохранён» only after successful `save_section`;
- «блок подтверждён» only after successful `confirm_section`;
- «интервью приостановлено/возобновлено» only after successful API result.

До NAILS-002E по-прежнему запрещено говорить:

- «рабочий график настроен»;
- «услуга добавлена в рабочий каталог»;
- «запись создана»;
- «свободные окна рассчитаны».

Confirmed onboarding data ещё не materialized into working business tables.

## CI

Plugin CI runs on Python 3.11 and 3.12 and checks:

- manifest structure;
- Ruff;
- trusted context identity;
- non-Telegram fail-closed behavior;
- spoofed identity argument rejection;
- fixed endpoint and body mapping;
- invalid action combinations;
- indistinguishable 401/403;
- stable request ID across retry;
- secret-safe transport failure;
- safe validation details.

## Production acceptance

Deployment is accepted only when:

- source copied exactly from merged commit;
- plugin enabled only in profile `nails`;
- Telegram toolsets add only `nails_onboarding`;
- existing safe toolsets remain;
- terminal/file/web/browser/code execution/MCP remain disabled;
- profile environment receives authentication setting without printing it;
- active admin/master can call start/get/save/confirm/pause/resume/complete;
- identity spoofing attempt cannot change owner;
- two users cannot read each other's state;
- unknown/inactive user receives safe refusal;
- pause/resume survives gateway restart;
- secrets are absent from logs and responses;
- synthetic data are removed.

## Out of scope

- automatic user provisioning;
- production interview skill;
- materialization into schedule/services/bookings;
- availability and booking operations;
- generic HTTP;
- direct SQL;
- aiogram.
