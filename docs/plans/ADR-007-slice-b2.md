# ADR-007 Slice B2 — catalog activation and booking overrides

Связано с #127 и родительским #122.

## Предусловие

Production baseline `9e219911a2878032bce7de048f21114ccb6a6b00` уже хранит booking catalog snapshots и защищает legacy fixed/base inserts.

## Решение

- каталог принимает `base|addon` и все четыре типа цены;
- addon не имеет собственного duration и buffers, только `extra_minutes`;
- booking request содержит одну base-услугу, упорядоченный список addons и необязательные явные overrides;
- booking snapshot остаётся единственным источником исторической композиции;
- legacy `price_amount` остаётся non-null только для совместимости, но неподтверждённые range/on-request значения не выдаются как финальная цена;
- day view и Telegram plugin показывают состав, ориентир, подтверждение цены и источник длительности.

## Агрегация цены

- все fixed: точная сумма;
- fixed + range: сумма нижних и верхних границ;
- один per-unit item: per-unit с сохранённой единицей;
- per-unit в смешанном составе: общий итог `on_request`, item-level semantics сохраняются;
- любой on-request: общий итог `on_request`;
- manual override задаёт финальную цену, но не стирает исходный catalog price type/min/max.

## Агрегация времени

```text
catalog duration = base.duration_minutes + sum(addon.extra_minutes)
```

Явный `duration_override_minutes` побеждает расчёт и сохраняется с `duration_source=manual_override`.

## Rollback

Migration `0012` обновляет trigger из B1. Предыдущий release:

- может создавать fixed/base booking;
- не может создать booking для activated addon/non-fixed service;
- получает отказ вместо тихой подмены range/on-request на legacy число.

## Не входит

- quantity для per-unit;
- compatibility matrix addons;
- per-client overrides;
- visit finalization, no-show, evening digest;
- photo import и public catalog.
