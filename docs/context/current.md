# Nails — текущий контекст для продолжения работы

Дата фиксации: **19 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR.

Не полагаться на память: GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Рабочий контракт

```text
repository: michailr1/Nails
GitHub main: 9e219911a2878032bce7de048f21114ccb6a6b00
production host: de.funti.cc
production repo: /opt/nails/repo
production branch: main
production SHA: 9e219911a2878032bce7de048f21114ccb6a6b00
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
health: /health
readiness: /ready
timezone: Europe/Moscow
Hermes plugins: nails-onboarding, nails-scheduling
```

Основной агент пишет код, тесты и документацию, управляет GitHub, review, CI и fast-forward merge. VPS-агент только выполняет утверждённый runbook и не меняет код или GitHub.

Обязательные постоянные правила:

- один живой Telegram-тест за раз;
- в GitHub используются только роли `master`, `admin`, `client`, без персональных имён;
- имя интерфейса и помощника — «Нэйли».

Релизы выполняются постоянным `ops/deploy/deploy.sh <exact-SHA>` по схеме PR → CI → candidate exact SHA → fast-forward того же SHA → finalize.

## Production milestone

ADR-007 Slice B1 развернут и финализирован:

```text
production SHA: 9e219911a2878032bce7de048f21114ccb6a6b00
previous SHA: 2c9f919dbb1a6266904a9b08f504fbb6f83f103b
API bind: 127.0.0.1:8210
candidate: success
production: success
backup: /opt/nails/backups/nails-before-deploy-20260719T163400Z.sql.gz
```

`bookings` имеют expand-only snapshot состава и исходной ценовой семантики. DB compatibility trigger заполняет snapshot при insert из предыдущего release.

## Текущая задача

Issue #127 — ADR-007 Slice B2: активация состава услуги, новых типов цены и overrides.

Рабочая ветка:

```text
feat/adr007-slice-b2-activation-overrides
baseline=9e219911a2878032bce7de048f21114ccb6a6b00
```

## Scope

- разрешить запись `addon`, `range`, `per_unit`, `on_request` в каталоге;
- запись содержит одну base-услугу и до 20 addons;
- длительность по умолчанию: base duration + addon `extra_minutes`;
- fixed цены складываются;
- fixed + range формируют итоговую вилку;
- single per-unit сохраняет цену и единицу, смешанный per-unit остаётся неподтверждённым ориентиром;
- on-request не отображается как подтверждённый ноль;
- мастер может явно переопределить итоговую цену и длительность;
- idempotency учитывает состав и overrides;
- day view и Telegram plugin возвращают полный неизменяемый snapshot.

## Rollback-контракт

Предыдущий production release понимает только одну fixed/base услугу. Миграция `0012` обновляет существующий DB trigger:

- legacy insert с `duration_source=catalog_snapshot` продолжает работать для fixed/base;
- legacy insert для addon или non-fixed base отклоняется;
- новый path пишет `duration_source=catalog_v2` либо `manual_override` и сохраняет полный snapshot.

Так rollback не создаёт тихо повреждённую запись, но обычные старые fixed/base записи остаются доступны.

## Инварианты

- confirmation каждой мутации;
- owner-scoping base, addons и clients;
- неизменяемые booking price/duration snapshots;
- ADR-006 day-off и overlap gate;
- idempotency;
- backup перед мутирующим deploy;
- успех только после `ok=true` и exact runtime SHA.

## Сознательно не входит

- количество для per-unit («за ноготь»);
- правила совместимости конкретных addons;
- per-client price overrides;
- вечерний дайджест и финализация визита;
- no-show flow;
- импорт прайса по фото;
- публичный прайс и клиентский контур.

## Точка продолжения

```text
1. завершить реализацию и regression tests issue #127
2. открыть draft PR к main
3. исправить CI на exact head
4. review rollback, owner-scoping и idempotency
5. перевести PR в Ready for review
6. candidate deployment exact PR head
7. fast-forward main тем же SHA
8. finalize production
```
