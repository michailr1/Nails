# Nails — обязательный контракт агентов

Этот файл обязателен для чтения **до любых действий** в новом контексте, новой сессии или новым агентом. Он действует для всего репозитория.

Обязательные нормативные документы:

- [`docs/context/current.md`](docs/context/current.md) — компактный актуальный handoff: production SHA, текущая задача, обнаруженные проблемы, принятые решения и точка продолжения;
- [`docs/operations/agent-responsibilities.md`](docs/operations/agent-responsibilities.md) — разделение ответственности основного и VPS-агента;
- [`docs/operations/production-infrastructure.md`](docs/operations/production-infrastructure.md) — проверенная production-топология, пути и правильный способ управления Hermes;
- [`docs/operations/hermes-plugin-runtime.md`](docs/operations/hermes-plugin-runtime.md) — точный контракт загрузки profile-local plugins, `plugins.enabled` и Telegram toolsets для установленной версии Hermes;
- [`docs/operations/engineering-principles.md`](docs/operations/engineering-principles.md) — обязательные инженерные принципы: соразмерность масштабу проекта, устранение класса ошибки вместо нового защитного слоя, правило вычитания, один постоянный deploy-скрипт (ADR-003), rollback как deploy предыдущего SHA.

Перед любыми действиями в новом контекстном окне основной агент обязан сначала прочитать `docs/context/current.md`, затем остальные operational-документы. Нельзя заново угадывать service manager, runtime paths, plugin keys, структуру конфигурации или release-flow по памяти предыдущего чата.

Если `docs/context/current.md` противоречит свежему GitHub, production preflight, коду `ops/deploy/deploy.sh` или более узкому deployment report, основной агент обязан остановиться, установить фактическое состояние и обновить нормативные документы через branch → PR → CI.

## Неизменяемая граница ответственности

### Основной агент ChatGPT

Основной агент ChatGPT — единственный исполнитель, который:

- анализирует требования, репозиторий, архитектуру и отчёты production;
- принимает технические, архитектурные и продуктовые решения;
- пишет, изменяет и удаляет код, тесты, миграции и документацию;
- создаёт ветки, коммиты, issues и pull requests;
- проводит review, исправляет замечания и проверяет CI;
- выполняет любые изменения в GitHub, включая merge;
- выбирает точный release SHA, source ref, критерии приёмки и rollback;
- формирует точный candidate/main-deploy/rollback runbook;
- закрывает issue только после требуемой production-приёмки.

### VPS-агент

VPS-агент — **только исполнитель заранее подготовленного runbook** на production-сервере.

Ему разрешено:

- выполнять точные команды из runbook без изменения их смысла;
- делать указанные backup, candidate deployment, main deployment, restart, verification и rollback;
- выполнять указанные диагностические проверки;
- до merge fetch точного PR head в заранее указанную `origin/pr/<number>` ref без изменения checkout;
- после merge запускать единый штатный main release через `ops/deploy/deploy.sh` для точного `origin/main` SHA;
- возвращать фактический отчёт без секретов.

VPS-агенту запрещено:

- писать, редактировать, исправлять или рефакторить код;
- самостоятельно менять тесты, миграции, документацию или конфигурацию;
- создавать ветки, коммиты, теги или pull requests;
- выполнять push, merge или любые изменения в GitHub;
- принимать архитектурные, технические или продуктовые решения;
- придумывать недостающие команды либо менять runbook;
- выполнять ad-hoc SQL, shell-исправления или ручные патчи приложения;
- вручную разделять, переставлять или пропускать шаги `ops/deploy/deploy.sh`;
- продолжать deployment после ошибки вне явно предусмотренного rollback.

## Правило остановки

При любой ошибке, расхождении SHA, неожиданном состоянии или неполной инструкции VPS-агент обязан:

1. остановить дальнейшие действия;
2. выполнить только встроенный rollback, если он уже предусмотрен runbook;
3. сохранить диагностику;
4. сообщить точный этап, команду/проверку, ошибку, checkout SHA, running SHA, состояние сервисов, путь backup и результат rollback;
5. **не исправлять проблему самостоятельно**.

Исправление всегда возвращается основному агенту ChatGPT и проходит обычный цикл: код → тесты → PR → CI → release validation.

## Git и GitHub

### PR candidate до merge

VPS-агент может fetch точного PR head в `origin/pr/<number>` и выполнить candidate deployment через постоянный `ops/deploy/deploy.sh`. Candidate SHA должен совпадать с заранее указанной ref, быть потомком production baseline, а production checkout обязан остаться на исходном SHA.

Candidate является дополнительной production validation до merge. Он допустим только для открытого PR-head SHA. После squash/rebase merge этот SHA не равен новому `main`, поэтому старый candidate нельзя выдавать за validation нового merge SHA.

### GitHub merge

Любое создание или изменение содержимого GitHub остаётся исключительной ответственностью основного агента ChatGPT. Метод merge выбирается осознанно до production validation. Нельзя утверждать, что rebase/squash SHA уже проверен candidate, если candidate запускался для другого PR-head SHA.

### Production release после merge

Отдельного finalize entrypoint в репозитории нет. После merge штатный поддерживаемый путь один:

```text
NAILS_RELEASE_REF=origin/main bash ops/deploy/deploy.sh <exact-main-SHA>
```

Этот main deploy сам:

1. fetch и проверяет `origin/main == exact SHA`;
2. проверяет clean checkout и ancestry;
3. создаёт detached release worktree;
4. создаёт и валидирует database/runtime backup;
5. собирает и проверяет API/WEB images;
6. останавливает только предусмотренные runtime-компоненты;
7. запускает миграции и новый runtime;
8. проверяет health/readiness/runtime SHA;
9. устанавливает plugins, skills и digest runtime;
10. только после успешных runtime-проверок fast-forward’ит локальный production checkout;
11. возвращает `DEPLOY_OK=true`.

Ручной «finalize» отдельной командой, локальный merge до или вместо `deploy.sh`, повторное развертывание уже работающего candidate либо обход встроенного backup/rollback не являются поддерживаемым flow.

## Обязательный порядок работы

1. Основной агент читает этот файл и operational source of truth.
2. Основной агент проверяет актуальный `main`, active issue и production state.
3. Основной агент создаёт ветку и вносит изменения.
4. Основной агент создаёт PR, проводит review и проверяет CI.
5. При необходимости VPS-агент выполняет candidate deployment точного открытого PR-head SHA из `origin/pr/<number>`; checkout не меняется.
6. Основной агент анализирует candidate report и выполняет GitHub merge.
7. Для точного смерженного `main` SHA VPS-агент выполняет единый штатный main deploy через `ops/deploy/deploy.sh`; отдельного finalize нет.
8. Основной агент проводит пользовательскую приёмку.
9. Основной агент обновляет `docs/context/current.md` после значимого production milestone или изменения точки продолжения.
10. Issue закрывает основной агент после выполнения всех критериев.

Любая инструкция, передающая VPS-агенту написание кода, исправление файлов, изменение GitHub или несуществующий release entrypoint, противоречит этому контракту и не должна выполняться.
