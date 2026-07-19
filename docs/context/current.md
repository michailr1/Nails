# Nails — текущий контекст для продолжения работы

Дата фиксации: **19 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR.

Не полагаться на память: GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Рабочий контракт

```text
repository: michailr1/Nails
GitHub main: 2c9f919dbb1a6266904a9b08f504fbb6f83f103b
production host: de.funti.cc
production repo: /opt/nails/repo
production branch: main
production SHA: 2c9f919dbb1a6266904a9b08f504fbb6f83f103b
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

ADR-007 Slice A развернут и финализирован:

```text
production SHA: 2c9f919dbb1a6266904a9b08f504fbb6f83f103b
API bind: 127.0.0.1:8210
health: ok
readiness: ok
working tree: clean
```

Каталог услуг получил schema/model для `base|addon` и `fixed|range|per_unit|on_request`, категории, сортировку и `extra_minutes`. Rollback-safe write gate пока разрешает только `base/fixed`.

## Текущая задача

Issue #125 — ADR-007 Slice B1: booking catalog snapshot baseline.

Продолжение после production rollout: issue #127 — Slice B2, активация состава услуги, новых типов цены и overrides.

Рабочая ветка:

```text
feat/adr007-slice-b-booking-snapshots
baseline=2c9f919dbb1a6266904a9b08f504fbb6f83f103b
```

## Phased rollout

Slice B1 — обязательный промежуточный release для смены rollback baseline:

1. expand-only добавить в `bookings` неизменяемый snapshot состава и ценовой семантики;
2. backfill существующих записей как один `base/fixed` item;
3. новый booking path заполняет snapshot для текущих разрешённых `base/fixed` услуг;
4. gates на `addon` и non-fixed цены остаются включены;
5. только после deployment следующий issue #127 активирует допы, range, per-unit, on-request и overrides.

Это предотвращает появление записей, которые предыдущий production SHA интерпретирует как неверную фиксированную цену.

## Инварианты

- confirmation каждой мутации;
- owner-scoping;
- booking price/duration snapshots;
- ADR-006 day-off и overlap gate;
- idempotency;
- expand-only миграция минимум на один релиз;
- backup перед мутирующим deploy;
- успех только после `ok=true` и exact runtime SHA.

## Сознательно не входит в Slice B1

- снятие catalog rollout gates;
- выбор addons в request/API/plugin;
- overrides цены и длительности;
- вечерний дайджест;
- импорт прайса по фото;
- публичный прайс и клиентский контур.

## Точка продолжения

```text
1. завершить review exact diff и rollback-контракта PR #126
2. получить зелёный CI на финальном head
3. перевести PR в Ready for review
4. candidate deployment exact PR head
5. fast-forward main тем же SHA
6. finalize production
7. начать issue #127 Slice B2 activation + overrides
```
