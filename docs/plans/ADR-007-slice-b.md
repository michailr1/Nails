# ADR-007 Slice B — booking catalog snapshots

Связано с issue #125 и ADR-007.

## Цель

Создать rollback-safe baseline для будущих допов и новых типов цены: каждая новая запись должна сохранять неизменяемый snapshot состава, исходной ценовой семантики и источника длительности.

## Существующие механизмы

- `Booking.service_id`, legacy `price_amount`, `duration_minutes_snapshot` и buffer snapshots;
- `create_booking()` и owner schedule lock;
- `calculate_reservation()` и ADR-006 overlap/day-off gate;
- idempotency key;
- `Service.kind`, `price_type`, range/unit fields из Slice A.

## Решение

- expand-only поля добавляются в существующую таблицу `bookings`;
- старые строки backfill как один `base/fixed` component;
- новые разрешённые `base/fixed` записи сразу получают полный snapshot;
- legacy columns остаются источником совместимости предыдущего release;
- rollout gates Slice A остаются включены до следующего production baseline.

## Что сознательно не входит

- addon selection;
- non-fixed writes;
- booking price/duration overrides;
- изменение plugin contract;
- вечерний дайджест и закрытие визита.

## Критерии приёмки

- существующие записи мигрируют без изменения legacy полей;
- clean и repeated migration проходят;
- новая fixed/base запись сохраняет один catalog item;
- snapshot содержит имя, kind, price type, цену, валюту и длительность;
- price semantics имеют отдельные min/max/unit поля;
- `on_request` может быть представлен без подтверждённого нуля после последующей активации;
- catalog changes не требуют изменения уже сохранённого snapshot;
- owner-scoping, idempotency и ADR-006 gate не меняются;
- предыдущий release может работать на расширенной схеме.

## Что удалено взамен добавленного

Параллельная таблица composition/V2 и новый booking endpoint не создаются. Расширяется существующая запись и существующий `create_booking()`.
