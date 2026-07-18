# ADR-005: безопасный web-интерфейс мастера

- Статус: принято
- Дата: 2026-07-17
- Обновлено: 2026-07-18

## Решение

Первый web-slice предназначен только для мастера и остаётся read-only. Он включает:

- Telegram tap-approve со сверкой шестизначного числа без ручного ввода кода;
- server-side session, logout и revoke;
- read-only календарь дня и недели;
- read-only список и карточки клиенток;
- owner-scoped CSV/Excel export календаря и клиенток;
- Host, Origin, session и BFF boundary;
- rate limits и kill-switch.

Mutation-CSRF переносится в write-slice. Write, admin/multi-master и revenue остаются в плане как отдельные gated slices.

## Login challenge

Web показывает verification number. Закрытый Telegram-бот показывает то же число и кнопку подтверждения. Мастер сверяет число и нажимает кнопку; вводить код в Telegram не требуется.

Challenge одноразовый, имеет короткий TTL и лимит попыток. Один pending challenge на browser scope обеспечивается `pending_scope_hash` и partial unique index только для `status = pending`.

Второй start имеет replace-семантику: предыдущий pending переводится в denied, затем создаётся новый. Advisory transaction lock упорядочивает замену, но инвариант обеспечивается базой данных.

## Gated slices

### Slice 1 — read-only, export и tap-approve

- auth challenge и server-side session;
- календарь дня и недели;
- клиентские карточки только для чтения;
- CSV/Excel export с owner scoping, лимитами, audit и защитой от formula injection;
- отсутствие web-мутаций предметных данных.

### Slice 2 — write

- создание, перенос и мягкая отмена записи;
- изменения availability, услуг и клиентских карточек;
- mutation-CSRF, idempotency, preview, fresh readback и повторная server-side validation.

### Slice 3 — admin/multi-master

Admin/multi-master остаётся отдельным gated slice. До него обязательны выделенные admin contracts, согласованная синхронизация мастеров и regression-тест изоляции по issue #88.

### Slice 4 — revenue

Выручка остаётся поздним gated slice после доказанной owner isolation и корректности read/write данных.

## Архитектурная граница

```text
Browser
  → HTTPS reverse proxy :<high-port>
  → web/BFF session boundary
  → owner-scoped domain services
  → PostgreSQL
```

Внутренний API остаётся loopback-only. ADR-006 применяется без изменений. Высокий нестандартный порт является только defense-in-depth; настоящими контролями остаются TLS, auth, sessions, owner scoping и rate limits.

## Security acceptance

До production должны быть подтверждены:

- неизвестный или неактивный пользователь не получает сессию;
- challenge нельзя использовать дважды или после TTL;
- один pending на scope гарантируется partial unique index;
- concurrent second start оставляет один pending и один denied;
- browser не может подменить identity или owner;
- logout и revoke прекращают доступ;
- export owner-scoped и защищён от formula injection;
- внутренний API остаётся loopback-only;
- публичная поверхность доступна только через утверждённый HTTPS reverse proxy;
- логи не содержат verification number, cookie или private content.

## Последствия

Первый slice даёт полезный read-only web без преждевременного write attack surface. Export входит в Slice 1. Mutation-CSRF становится release blocker для Slice 2. Поздние slices не удаляются из roadmap.
