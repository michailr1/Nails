# Разделение ответственности между основным и VPS-агентом

Статус: **обязательный проектный контракт**.

Краткая обязательная версия находится в корневом [`AGENTS.md`](../../AGENTS.md). При расхождении старые документы и prompts приводятся к этому контракту и фактическому поведению `ops/deploy/deploy.sh`.

## 1. Основной принцип

Разработка, GitHub и production execution разделены:

- **Основной агент создаёт изменения и единолично меняет GitHub.**
- **VPS-агент исполняет точные diagnostic/candidate/main-deploy/rollback команды.**
- **Ни один агент не должен выдумывать release entrypoint, которого нет в репозитории.**

Доступ VPS-агента к shell не превращает его в разработчика или GitHub-оператора.

## 2. Исключительная ответственность основного агента

Только основной агент:

- анализирует требования, репозиторий, CI и production reports;
- принимает архитектурные, security, schema, API и продуктовые решения;
- пишет и изменяет application code, tests, migrations, configuration templates и documentation;
- создаёт branches, commits, issues и pull requests;
- проводит review и проверяет CI;
- определяет точные candidate/release SHA, source ref, acceptance criteria и rollback;
- анализирует production reports;
- выполняет GitHub merge;
- выдаёт main-deploy команду после GitHub merge;
- фиксирует production result и закрывает issue после acceptance.

Основной агент не просит VPS-агента исправлять код, делать commit, push, PR или GitHub merge.

## 3. Разрешённые действия VPS-агента

В рамках конкретной точной команды VPS-агент может:

- выполнять read-only preflight и диагностику;
- fetch точного PR head в заранее указанную remote-tracking ref;
- проверить candidate/release SHA и clean production checkout;
- создать и проверить database/runtime backup через штатный deploy-flow;
- выполнить candidate deployment заранее подготовленного открытого PR-head SHA;
- выполнить единый production deployment точного смерженного `origin/main` SHA;
- перезапустить только явно названные containers/services либо те, которыми управляет штатный скрипт;
- выполнить production verification;
- выполнить встроенный rollback при ошибке;
- вернуть компактный фактический отчёт.

Candidate deployment из `origin/pr/<number>` **не меняет локальный production checkout**. После merge отдельного finalize entrypoint нет: main deployment повторно выполняет полный безопасный release-flow для точного нового main SHA и только после успешной runtime-проверки fast-forward’ит checkout.

## 4. Безусловные запреты VPS-агенту

VPS-агент не имеет права:

- писать, редактировать или исправлять tracked code/files;
- менять tests или migrations ради прохождения проверки;
- создавать branch, commit, tag или pull request;
- выполнять `git push`;
- выполнять merge или иные изменения в GitHub;
- выбирать другой SHA, source ref или rollback target;
- принимать архитектурные, security, schema или продуктовые решения;
- заменять команду «эквивалентной»;
- выполнять произвольный SQL или изменять production data для обхода ошибки;
- менять secrets, permissions, firewall или allowlist без точной команды;
- раскрывать secrets и персональные данные;
- вручную выполнять только часть `deploy.sh`, переставлять или пропускать его шаги;
- продолжать после failed assertion вне встроенного rollback;
- повторять deployment без новой инструкции основного агента.

## 5. Git и проверенный SHA

### Candidate phase — до merge

1. Основной агент создаёт PR и проверяет CI/review.
2. Основной агент называет точный PR-head SHA и PR number.
3. VPS fetch выполняется только в ref вида `origin/pr/<number>`.
4. Проверяется, что ref равен указанному SHA и candidate является потомком текущего production checkout.
5. Candidate строится из отдельного worktree точного SHA.
6. Runtime запускается с `NAILS_GIT_SHA=<candidate SHA>`.
7. Production checkout остаётся на исходном SHA.

Candidate — дополнительная production validation открытого PR-head SHA. Если GitHub merge создаёт другой SHA, например rebase/squash commit, этот новый SHA требует собственного штатного main deployment и не считается уже проверенным candidate.

### GitHub merge — только основной агент

После CI/review и, когда требуется, успешного candidate report основной агент выполняет GitHub merge. Метод merge выбирается до production validation и должен учитывать, сохранится ли SHA.

VPS-агент не выполняет GitHub merge и не меняет remote refs.

### Main deployment — после merge

Поддерживаемый production entrypoint:

```text
cd /opt/nails/repo
NAILS_RELEASE_REF=origin/main bash ops/deploy/deploy.sh <exact-main-SHA>
```

Штатный main deploy:

1. fetch `origin/main`;
2. проверяет `origin/main == exact-main-SHA`;
3. проверяет commit object, ancestry и clean checkout;
4. создаёт detached release worktree;
5. создаёт и валидирует database/runtime backup до runtime mutation;
6. собирает и проверяет API/WEB images;
7. останавливает digest timer и Hermes gateway в предусмотренной скриптом последовательности;
8. запускает миграции и новый runtime;
9. проверяет runtime SHA, API health/readiness и web;
10. устанавливает plugins, skills, backup runtime и digest runtime;
11. после успеха выполняет локальный `git merge --ff-only <exact-main-SHA>`;
12. возвращает `DEPLOY_OK=true`.

Отдельного finalize script/entrypoint нет. Локальный `git merge --ff-only` не должен выдаваться VPS-агенту отдельной командой вместо штатного main deploy.

## 6. Поведение при ошибке

При расхождении hostname/path/SHA/ref, dirty tree, невалидном backup, failed health, неожиданном service state или необходимости что-то исправить VPS-агент:

1. останавливается;
2. выполняет только встроенный rollback, если он применим;
3. не редактирует файлы и не выполняет ad-hoc SQL;
4. не повторяет deployment;
5. сообщает phase, failed command/assertion, безопасную ошибку, checkout SHA, running SHA, backup path и rollback result.

После этого проблема возвращается основному агенту в цикл branch → test → PR → CI → release validation.

## 7. Обязательный заголовок VPS-команды

```text
РОЛЬ И ГРАНИЦА ОТВЕТСТВЕННОСТИ

Ты — VPS-агент проекта Nails. Ты только исполняешь точную diagnostic,
candidate, main-deploy или rollback команду на production-сервере.

Основной агент уже выполнил анализ, написал код, создал PR, провёл review,
проверил CI и выбрал точный SHA. Любые изменения GitHub выполняет только
основной агент.

Тебе запрещено писать или исправлять код, менять tracked files, создавать
commit/branch/tag/PR, выполнять push или GitHub merge, менять команду,
принимать решения, вручную разделять deploy.sh и самостоятельно устранять ошибку.

При ошибке остановись, выполни только встроенный rollback и верни фактический отчёт.
```

## 8. Нормальный release flow

```text
Основной агент: branch → code/docs/tests
        ↓
PR → review → CI
        ↓
опционально VPS: candidate открытого PR-head из origin/pr/<N>
        ↓
Основной агент: GitHub merge
        ↓
VPS: единый main deployment exact origin/main SHA через deploy.sh
        ↓
DEPLOY_OK=true + checkout/runtime SHA verification
        ↓
Основной агент: acceptance → status → issue closure
```

## 9. Закрытие issues

Успешный candidate deployment сам по себе не закрывает issue. Основной агент обязан проверить финальный main-deploy report, убедиться в совпадении checkout/runtime SHA, провести требуемую приёмку и только затем зафиксировать production status.
