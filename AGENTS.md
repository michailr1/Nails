# Nails — обязательный контракт агентов

Этот файл обязателен для чтения **до любых действий** в новом контексте, новой сессии или новым агентом. Он действует для всего репозитория.

Обязательные нормативные документы:

- [`docs/context/current.md`](docs/context/current.md) — актуальная точка продолжения;
- [`docs/product/product-principles.md`](docs/product/product-principles.md) — продуктовая философия и терминология;
- [`docs/operations/agent-responsibilities.md`](docs/operations/agent-responsibilities.md) — разделение ответственности;
- [`docs/operations/production-infrastructure.md`](docs/operations/production-infrastructure.md) — production topology;
- [`docs/operations/hermes-plugin-runtime.md`](docs/operations/hermes-plugin-runtime.md) — Hermes runtime contract;
- [`docs/operations/engineering-principles.md`](docs/operations/engineering-principles.md) — инженерные принципы и release discipline.

Перед любыми действиями в новом контексте основной агент обязан **сначала прочитать `docs/context/current.md`**. Нельзя заново угадывать runtime paths, service manager, release-flow, plugin keys или фактический production state по памяти предыдущего чата.

Exact production checkout/origin/running SHA **не self-pin'ится как вечный факт**. Для candidate/release exact refs всегда устанавливаются свежим GitHub ref и read-only production preflight.

Если tracked docs противоречат свежему GitHub, production preflight или фактическому коду deploy/candidate entrypoints, основной агент обязан сначала установить фактическое состояние и исправить документы через branch → PR → CI.

## Неизменяемая граница ответственности

### Основной агент ChatGPT

Основной агент ChatGPT — единственный исполнитель, который:

- анализирует требования, код, архитектуру и production reports;
- принимает рядовые технические/архитектурные решения;
- пишет код, тесты, миграции и документацию;
- создаёт/обновляет issues, branches и PR;
- проводит review, проверяет CI и выполняет merge;
- выбирает exact candidate/release SHA;
- формирует candidate/deploy/rollback runbook;
- закрывает issue после требуемой приёмки.

### VPS-агент

VPS-агент — **только исполнитель заранее подготовленного runbook**.

Ему разрешено:

- выполнять точные candidate/deploy/diagnostic/rollback команды;
- делать предусмотренные backup и runtime checks;
- fetch exact refs, требуемые runbook;
- возвращать фактический отчёт без секретов.

Ему запрещено:

- писать, редактировать, исправлять или рефакторить код, тесты, миграции или tracked docs;
- создавать commits/branches/PR, выполнять push, merge или любые изменения в GitHub;
- принимать архитектурные решения;
- делать ad-hoc SQL/source/.env fixes;
- продолжать после fail-closed вне явно предусмотренного rollback.

## Правило остановки

При ошибке, расхождении SHA или неожиданном runtime state VPS-агент:

1. останавливает дальнейшие действия;
2. выполняет только предусмотренный rollback;
3. сохраняет диагностику;
4. сообщает exact refs, failing stage, runtime state и backup;
5. не исправляет проблему самостоятельно.

## Git и GitHub

### PR candidate до merge

Нормативный pre-merge candidate entrypoint — **изолированный adapter**:

```text
ops/deploy/candidate_deploy.sh
```

Candidate:

- строится из exact открытого PR-head;
- использует отдельный Compose project, ports/networks/volume;
- не использует production DB/env/runtime;
- не меняет production checkout;
- не запускает конкурирующий client bot на production Telegram token;
- после проверки очищает candidate resources.

`ops/deploy/deploy.sh` — **не candidate entrypoint**. Это единственный постоянный production deploy path.

Candidate PR-head и будущий merge SHA могут отличаться при merge commit/squash/rebase. Поэтому pre-merge candidate доказывает корректность дерева PR, но после merge exact `main` всё равно проверяется CI/preflight и деплоится как отдельный exact release. Нельзя выдавать PR-head SHA за running main SHA.

### GitHub merge

GitHub changes и merge выполняет основной агент. Merge method выбирается в соответствии с текущим repository policy. После merge источник истины — фактический `origin/main` SHA.

### Production release после merge

Отдельного finalize entrypoint в репозитории нет.

Поддерживаемый production path:

```text
NAILS_RELEASE_REF=origin/main bash ops/deploy/deploy.sh <exact-main-SHA>
```

Production deploy:

1. проверяет exact `origin/main`;
2. проверяет clean checkout/ancestry;
3. создаёт release worktree;
4. делает и валидирует backup;
5. собирает runtime images;
6. запускает migrations/runtime;
7. проверяет health/readiness/running SHA;
8. проверяет client runtime invariants при enabled;
9. обновляет локальный production checkout только после успешной проверки;
10. возвращает `DEPLOY_OK=true`.

Rollback = штатный deploy предыдущего exact SHA. Ручного finalize или ручных source/DB fixes нет.

## Client runtime invariants

- один платформенный client bot обслуживает нескольких мастеров;
- client API и bot flags включаются/выключаются только вместе;
- master/client Telegram tokens различаются;
- client runtime не имеет direct DB access;
- на одном token должен быть один активный runtime;
- legacy host client-bot runtime должен быть inactive;
- `start_token -> owner_user_id` резолвится только сервером.

## Обязательный порядок работы

1. Прочитать этот файл и current context.
2. Проверить fresh `main`, relevant issues и production state.
3. Создать branch и внести изменения.
4. Создать PR, review, CI.
5. Если runtime change требует pre-merge acceptance — VPS выполняет candidate deployment точного открытого PR-head SHA через isolated candidate path.
6. Основной агент анализирует report и выполняет merge.
7. Для runtime release VPS выполняет exact-main production deploy.
8. Основной агент проводит пользовательскую acceptance.
9. Основной агент обновляет `docs/context/current.md` после значимого production milestone или изменения точки продолжения.
10. Issue закрывает основной агент после выполнения его актуальных критериев.

Пользователь не должен выдавать пошаговые технические задания, если следующий безопасный шаг основной агент может определить сам.
