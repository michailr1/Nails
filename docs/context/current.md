# Nails — текущий контекст

Дата фиксации: **19 июля 2026 года**.

Перед работой прочитать `AGENTS.md`, `docs/context/current.md`, `docs/operations/engineering-principles.md`, остальные operational-документы и принятые ADR. GitHub проверять по API, production — фактическим preflight. **Production state не предполагать**.

## Базовое состояние

```text
repository: michailr1/Nails
GitHub main: fea7f3598b987842e86dba57bb7c2d4db574e410
production host: de.funti.cc
production repo: /opt/nails/repo
production branch: main
production SHA: fea7f3598b987842e86dba57bb7c2d4db574e410
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

ADR-007 Slice D развернут на production. Работают финализация визитов, no-show, поздние корректировки и ежедневный дайджест в 23:30 по Москве. Живая проверка подтвердила одну отправку и отсутствие дубля при повторном запуске.

## Текущая задача

```text
issue=143
PR=144
branch=feat/adr007-slice-e-photo-price-import
baseline=fea7f3598b987842e86dba57bb7c2d4db574e410
```

Slice E добавляет занесение прайса по фото:

- изображения разбираются существующим vision-инструментом;
- backend не распознаёт и не хранит изображения;
- Нэйли показывает одну редактируемую таблицу;
- длительности явно помечаются как предложение Нэйли;
- одна confirmation применяет весь каталог одной owner-scoped транзакцией;
- новые позиции создаются, совпавшие по имени обновляются, отсутствующие активные позиции архивируются;
- некорректная строка отклоняет весь batch;
- повтор одинакового batch идемпотентен;
- существующие booking snapshots не изменяются;
- readback не содержит внутренних ID.

## Точка продолжения

```text
1. получить green CI на exact PR head
2. провести self-review
3. перевести PR #144 в Ready for review
4. candidate deployment
5. fast-forward exact SHA
6. finalize production
7. одна живая Telegram-проверка по фото прайса
```
