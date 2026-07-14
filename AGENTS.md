# Nails — обязательный контракт агентов

Этот файл обязателен для чтения **до любых действий** в новом контексте, новой сессии или новым агентом. Он действует для всего репозитория.

Обязательные нормативные документы:

- [`docs/context/current.md`](docs/context/current.md) — компактный актуальный handoff: production SHA, текущая задача, обнаруженные проблемы, принятые решения и точка продолжения;
- [`docs/operations/agent-responsibilities.md`](docs/operations/agent-responsibilities.md) — разделение ответственности основного и VPS-агента;
- [`docs/operations/production-infrastructure.md`](docs/operations/production-infrastructure.md) — проверенная production-топология, пути и правильный способ управления Hermes;
- [`docs/operations/hermes-plugin-runtime.md`](docs/operations/hermes-plugin-runtime.md) — точный контракт загрузки profile-local plugins, `plugins.enabled` и Telegram toolsets для установленной версии Hermes;
- [`docs/operations/engineering-principles.md`](docs/operations/engineering-principles.md) — обязательные инженерные принципы: соразмерность масштабу проекта, устранение класса ошибки вместо нового защитного слоя, правило вычитания, один постоянный deploy-скрипт (ADR-003), rollback как deploy предыдущего SHA.

Перед любыми действиями в новом контекстном окне основной агент обязан сначала прочитать `docs/context/current.md`, затем остальные три operational-документа. Нельзя заново угадывать service manager, runtime paths, plugin keys, структуру конфигурации или правила видимости tools по памяти предыдущего чата.

Если `docs/context/current.md` противоречит свежему GitHub, production preflight или более узкому deployment report, основной агент обязан остановиться, установить фактическое состояние и обновить handoff через branch → PR → CI → candidate validation → merge.

## Неизменяемая граница ответственности

### Основной агент ChatGPT

Основной агент ChatGPT — единственный исполнитель, который:

- анализирует требования, репозиторий, архитектуру и отчёты production;
- принимает технические, архитектурные и продуктовые решения;
- пишет, изменяет и удаляет код, тесты, миграции и документацию;
- создаёт ветки, коммиты, issues и pull requests;
- проводит review, исправляет замечания и проверяет CI;
- оценивает candidate report и выполняет fast-forward merge проверенного PR-head SHA;
- выполняет другие изменения в GitHub;
- формирует точный candidate/finalize/rollback runbook;
- закрывает issue только после требуемой production-приёмки.

### VPS-агент

VPS-агент — **только исполнитель заранее подготовленного runbook** на production-сервере.

Ему разрешено:

- выполнять точные команды из runbook без изменения их смысла;
- делать указанные backup, candidate deployment, restart, verification и rollback;
- выполнять указанные диагностические проверки;
- копировать в runtime уже проверенные candidate-файлы;
- до merge fetch точного PR head в заранее указанную `origin/pr/<number>` ref без изменения checkout;
- после GitHub merge обновлять локальный checkout только через указанный `git merge --ff-only` до того же проверенного SHA;
- возвращать фактический отчёт без секретов.

VPS-агенту запрещено:

- писать, редактировать, исправлять или рефакторить код;
- самостоятельно менять тесты, миграции, документацию или конфигурацию;
- создавать ветки, коммиты, теги или pull requests;
- выполнять push, merge или любые изменения в GitHub;
- принимать архитектурные, технические или продуктовые решения;
- придумывать недостающие команды либо менять runbook;
- выполнять ad-hoc SQL, shell-исправления или ручные патчи приложения;
- продолжать deployment после ошибки вне явно предусмотренного rollback.

## Правило остановки

При любой ошибке, расхождении SHA, неожиданном состоянии или неполной инструкции VPS-агент обязан:

1. остановить дальнейшие действия;
2. выполнить только заранее описанный rollback, если он уже предусмотрен runbook;
3. сохранить диагностику;
4. сообщить точный этап, команду/проверку, ошибку, checkout SHA, running SHA, состояние сервисов, путь backup и результат rollback;
5. **не исправлять проблему самостоятельно**.

Исправление всегда возвращается основному агенту ChatGPT и проходит обычный цикл: код → тесты → PR → CI → candidate validation → merge → finalize.

## Git и GitHub

До merge VPS-агент может fetch точного PR head и выполнить candidate deployment. Candidate SHA должен совпадать с заранее указанной ref, а production checkout обязан остаться на исходном SHA.

После успешного candidate report основной агент fast-forward’ом перемещает GitHub `main` **на тот же проверенный PR-head SHA**. Squash, rebase и merge commit для production release запрещены, потому что создают новый непроверенный SHA. Если `main` изменился, merge останавливается и candidate проходит rollback либо повторную validation после rebase.

После GitHub fast-forward VPS-агент только проверяет `origin/main`, running `NAILS_GIT_SHA`, health/gateway и делает локальный `git merge --ff-only`.

Любое создание или изменение содержимого GitHub остаётся исключительной ответственностью основного агента ChatGPT.

## Обязательный порядок работы

1. Основной агент читает этот файл и operational source of truth.
2. Основной агент проверяет актуальный `main`, active issue и production state.
3. Основной агент создаёт ветку и вносит изменения.
4. Основной агент создаёт PR, проводит review и проверяет CI.
5. VPS-агент выполняет candidate deployment точного PR-head SHA, не меняя production checkout.
6. Основной агент анализирует отчёт и только при успехе fast-forward’ом мержит тот же SHA в GitHub `main`.
7. VPS-агент выполняет finalize локального checkout на уже смерженный SHA.
8. Основной агент проводит пользовательскую приёмку.
9. Основной агент обновляет `docs/context/current.md` после значимого production milestone или изменения точки продолжения.
10. Issue закрывает основной агент после выполнения всех критериев.

Любая инструкция, передающая VPS-агенту написание кода, исправление файлов или изменение GitHub, противоречит этому контракту и не должна выполняться.
