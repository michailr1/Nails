# ADR-003: один постоянный deploy-скрипт

- Статус: принято
- Дата: 2026-07-14

## Контекст

К моменту NAILS-002E6 на деплой приложения из двух контейнеров накопилось ~3500 строк bash: отдельный runbook на каждый релиз, хуки сохранения и восстановления образов, ручные списки ожидаемых маршрутов. Деплой E6 неоднократно собирал или запускал не тот код. Дополнительный инцидент показал, что merge до production validation создаёт расхождения между GitHub, checkout и running image.

## Решение

1. **Deploy-скрипт один — `ops/deploy/deploy.sh`.** Новые per-release entrypoint'ы запрещены.
2. **Production validation выполняется до GitHub merge.** Для open PR основной агент указывает `NAILS_RELEASE_REF=origin/pr/<number>` и точный PR-head SHA. Candidate строится из detached worktree и не меняет production checkout.
3. **Основной агент мержит только проверенный SHA.** После успешного candidate report GitHub `main` перемещается fast-forward’ом на тот же PR-head SHA. Squash, rebase и merge commit запрещены, потому что создают новый непроверенный SHA.
4. **После merge выполняется finalize checkout.** VPS проверяет `origin/main`, running `NAILS_GIT_SHA`, API и gateway, затем делает только локальный `git merge --ff-only` на тот же SHA. Runtime повторно не пересобирается.
5. **Тождество кода проверяется по SHA, зашитому в image.** Собранный image проверяется до остановки runtime, running container — после запуска.
6. **Скрипт исполняется только из regular root-only файла.** Запуск через pipe/stdin запрещён; `compose exec` изолирует stdin через `/dev/null`.
7. **Rollback использует записанный исходный checkout SHA** и остаётся решением основного агента.

## Последствия

- Код, прошедший production validation, и код в GitHub `main` имеют один и тот же SHA.
- VPS-агент не меняет GitHub и не выбирает merge или rollback target.
- Жёстко заданный baseline из прошлого запуска больше не используется: скрипт фиксирует фактический clean checkout перед candidate deployment.
- Если `main` изменился между validation и merge, candidate не мержится без rollback или повторной validation.
