# Разделение ответственности между основным и VPS-агентом

Статус: **обязательный проектный контракт**.

Краткая обязательная версия находится в корневом [`AGENTS.md`](../../AGENTS.md). При расхождении старые документы и prompts приводятся к этому контракту.

## 1. Основной принцип

Разработка, production validation и GitHub merge разделены:

- **Основной агент создаёт изменения и единолично меняет GitHub.**
- **VPS-агент исполняет точные candidate/finalize/diagnostic команды.**
- **GitHub merge выполняется основным агентом только после успешного candidate report.**

Доступ VPS-агента к shell не превращает его в разработчика или GitHub-оператора.

## 2. Исключительная ответственность основного агента

Только основной агент:

- анализирует требования, репозиторий, CI и production reports;
- принимает архитектурные, security, schema, API и продуктовые решения;
- пишет и изменяет application code, tests, migrations, configuration templates и documentation;
- создаёт branches, commits, issues и pull requests;
- проводит review и проверяет CI;
- определяет точные candidate SHA, source ref, acceptance criteria и rollback;
- анализирует candidate report;
- fast-forward’ом перемещает GitHub `main` на **тот же проверенный PR-head SHA**;
- выдаёт finalize-команду после GitHub merge;
- фиксирует production result и закрывает issue после acceptance.

Основной агент не просит VPS-агента исправлять код, делать commit, push, PR или GitHub merge.

## 3. Разрешённые действия VPS-агента

В рамках конкретной точной команды VPS-агент может:

- выполнять read-only preflight и диагностику;
- fetch точного PR head в заранее указанную remote-tracking ref;
- проверить candidate SHA и clean production checkout;
- создать и проверить database/runtime backup;
- выполнить candidate deployment заранее подготовленного SHA;
- перезапустить только явно названные containers/services;
- выполнить production verification;
- выполнить встроенный rollback при ошибке;
- после GitHub merge проверить тот же SHA и выполнить локальный `git merge --ff-only`;
- вернуть компактный фактический отчёт.

Candidate deployment **не меняет локальный production checkout**. Finalize не пересобирает приложение: он проверяет running SHA, `origin/main`, API и gateway, затем синхронизирует checkout.

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

### GitHub merge — только основной агент

После успешного candidate report основной агент проверяет, что GitHub `main` не изменился, и выполняет **fast-forward merge PR head → main**. Squash, rebase и merge commit запрещены: они создают SHA, который не проходил production validation.

Если `main` изменился, merge останавливается. Candidate откатывается либо branch перебазируется и проходит CI + production validation заново.

### Finalize phase — после merge

VPS-агент:

1. fetch `origin/main`;
2. проверяет `origin/main == validated SHA`;
3. проверяет `running NAILS_GIT_SHA == validated SHA`;
4. проверяет API и gateway;
5. выполняет локальный `git merge --ff-only <validated SHA>`;
6. возвращает finalize report.

Это не является GitHub merge и не даёт VPS-агенту права менять GitHub.

## 6. Поведение при ошибке

При расхождении hostname/path/SHA/ref, dirty tree, невалидном backup, failed health, неожиданном service state или необходимости что-то исправить VPS-агент:

1. останавливается;
2. выполняет только встроенный rollback, если он применим;
3. не редактирует файлы и не выполняет ad-hoc SQL;
4. не повторяет deployment;
5. сообщает phase, failed command/assertion, безопасную ошибку, checkout SHA, running SHA, backup path и rollback result.

После этого проблема возвращается основному агенту в цикл branch → test → PR → CI → candidate validation.

## 7. Обязательный заголовок VPS-команды

```text
РОЛЬ И ГРАНИЦА ОТВЕТСТВЕННОСТИ

Ты — VPS-агент проекта Nails. Ты только исполняешь точную candidate,
finalize, rollback или diagnostic команду на production-сервере.

Основной агент уже выполнил анализ, написал код, создал PR, провёл review,
проверил CI и выбрал точный SHA. GitHub merge выполнит основной агент только
после успешного candidate report.

Тебе запрещено писать или исправлять код, менять tracked files, создавать
commit/branch/tag/PR, выполнять push или GitHub merge, менять команду,
принимать решения и самостоятельно устранять ошибку.

При ошибке остановись, выполни только встроенный rollback и верни фактический отчёт.
```

## 8. Нормальный release flow

```text
Основной агент: branch → code/docs/tests
        ↓
PR → review → CI (PR остаётся open)
        ↓
VPS: candidate deployment точного PR-head SHA
        ↓
VPS: candidate report, checkout не изменён
        ↓
Основной агент: анализ report
        ↓
Основной агент: fast-forward PR-head SHA → GitHub main
        ↓
VPS: finalize локального checkout на тот же SHA
        ↓
Основной агент: acceptance → status → issue closure
```

## 9. Закрытие issues

Успешный candidate deployment сам по себе не закрывает issue. Основной агент обязан проверить candidate report, выполнить GitHub fast-forward, получить finalize report, провести ручную приёмку и только затем зафиксировать production status.
