# Nails — текущий контекст

Дата фиксации: **20 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Базовое состояние

```text
repository: michailr1/Nails
GitHub main: 74346e902f2ff87e30cf967b52a26c16cc556f88
production host: de.funti.cc
production repo: /opt/nails/repo
production branch: main
production SHA: 74346e902f2ff87e30cf967b52a26c16cc556f88
backend env: /opt/nails/.env
internal API: http://127.0.0.1:8210
health: /health
readiness: /ready
timezone: Europe/Moscow
Hermes plugins: nails-onboarding, nails-scheduling
```

Основной агент пишет код, тесты и документацию, управляет GitHub, CI, review и fast-forward. VPS-агент только выполняет утверждённые deployment-команды.

Обязательные правила:

- один живой Telegram-тест за раз;
- роли только `master`, `admin`, `client`;
- имя помощника — «Нэйли»;
- каждая мутация требует подтверждения;
- успех определяется только подтверждённым tool-результатом;
- релиз: PR → CI → candidate exact SHA → fast-forward того же SHA → finalize;
- deploy выполняется только через `ops/deploy/deploy.sh <exact-SHA>`.

## Завершённый этап

ADR-007 Slice E развернут на production. Работает импорт полного каталога услуг по одному или нескольким фото прайса через существующий vision-инструмент: Нэйли показывает единую редактируемую таблицу, отдельно помечает предложенные длительности как свою оценку и применяет каталог одной подтверждённой owner-scoped batch-мутацией. Живая Telegram-проверка успешна. По обратной связи оценка длительности может быть слегка завышена, но мастер корректирует её до подтверждения.

## Следующий приоритет

Вернуться к WEB-контуру. Безопасная последовательность остаётся:

1. завершить web auth/session/CSRF и browser security gate;
2. выпустить read-only календарь и просмотр записей;
3. сразу после этого добавить первый write-slice для мастера: редактирование каталога услуг в веб-интерфейсе;
4. затем редактирование графика и записей.

Редактирование услуг в вебе поднято в приоритете: оно не должно ждать полного web-кабинета или клиентского контура. Первый write-slice должен переиспользовать существующую backend-валидацию и подтверждённую batch-модель каталога, без отдельной логики данных во frontend.

## Точка продолжения

```text
1. закрыть issue #143 после фиксации live acceptance
2. восстановить фактический статус WEB-001 на main
3. завершить auth/session/CSRF blockers
4. read-only calendar
5. web service catalog editor as first write slice
```
