# Nails — текущий контекст для продолжения работы

Дата фиксации: **16 июля 2026 года**.

Сначала прочитать [`../../AGENTS.md`](../../AGENTS.md), затем этот файл, [`../operations/engineering-principles.md`](../operations/engineering-principles.md), [`../operations/production-infrastructure.md`](../operations/production-infrastructure.md) и [`../operations/hermes-plugin-runtime.md`](../operations/hermes-plugin-runtime.md).

Это handoff для нового контекста основного агента. Не угадывай состояние по памяти — проверяй по GitHub, а для production — по фактическому preflight.

## 1. Рабочий контракт

```text
repository: michailr1/Nails
production hostname: de.funti.cc
production repo: /opt/nails/repo
backend env: /opt/nails/.env
backend API: http://127.0.0.1:8210
Hermes profile: /root/.hermes/profiles/nails
production branch: main
```

- основной агент пишет код, меняет GitHub, проводит review/CI, мержит и готовит точные runbooks;
- VPS-агент только исполняет утверждённый runbook и возвращает компактный отчёт (`docs/operations/vps-reporting.md`);
- один живой Telegram-тест за раз;
- в GitHub — только роли (`master`, `admin`, `client`), без персональных имён; имя ассистента мастера — «Нэйли».

## 2. Деплой — один постоянный скрипт (ADR-003)

Все релизы идут через `ops/deploy/deploy.sh <exact-SHA>`. Одноразовые релизные runbook'и запрещены (CI-гейт `deploy-script.yml`). Поток: PR → CI → candidate-validation VPS-агентом по точному PR-head SHA (`NAILS_RELEASE_REF=origin/pr/<n>`, checkout не меняется) → основной агент fast-forward-мержит **тот же** SHA → VPS finalize `git merge --ff-only`. Rollback = `deploy.sh <prev-SHA>`. Тождество кода — по `NAILS_GIT_SHA`, зашитому в образ.

Исторические E4/E5/E6-runbook'и неактивны, VPS-агенту не выдаются. Их безопасные инварианты Hermes и деплоя живут в `production-infrastructure.md` и `hermes-plugin-runtime.md` — читать оттуда, не по памяти.

**Production state не предполагать.** `deploy.sh` сам фиксирует фактический clean checkout перед candidate-деплоем; жёстко заданные baseline из прошлых запусков запрещены (engineering-principles §3.6). Актуальный HEAD и версии плагинов устанавливаются preflight'ом, а не из этого документа.

## 3. Что уже в production-контуре

```text
backend: FastAPI + PostgreSQL, Alembic серии 000x
Hermes profile nails: gateway root user-level systemd (XDG_RUNTIME_DIR=/run/user/0 systemctl --user)
plugins: nails-onboarding, nails-scheduling (profile-local, restricted)
```

Работает: онбординг-интервью и materialization в рабочие таблицы; управление услугами (create/update/archive/restore со snapshot цен); календарь и доступность на конкретные даты; клиентки (exact + candidate поиск); создание/перенос/отмена записей (guarded read→write→readback в одном tool-вызове, `verified=true`). Персона «Нэйли»: «вы» по умолчанию, вопрос «ты/вы», одно имя, BotFather-имя выставлено (#70 закрыт).

## 4. Состояние PR

Уже смержены (предохранители против грабель §6 включены):

- **#63** — правило «перечисли существующие механизмы до проектирования» + ревью границ абстракций (`engineering-principles` §4, поле PR «Существующие механизмы»);
- **#78** — правило «CI-lint чинится только `ruff --fix`, руками импорты не трогать»;
- **#80** — ADR-004: клиентский контур v1 = детерминированный бот без LLM.

Открыт и **не готов**:

- **#81** `fix/client-card-guidance` — расширенные поля карточки клиентки, см. §5.

## 5. Активная работа: PR #81 — два дефекта за Ruff

Ruff на #81 починен автофиксом. Он обнажил два pytest-провала, которые прятались за Ruff (pytest не запускался после его падения) — они **не** от автофикса:

```text
test_read_clients.py::test_create_client_performs_exact_lookup_before_post
test_read_clients.py::test_create_client_returns_existing_without_post
```

Причина и правильный фикс — устранить дубликат, а не чинить моки:

- `create_client` переехал в новый модуль `client_cards.create_client_card` (`tools.py`), берущий `_call_backend` из `.transport`;
- старый `operations._create_client` делает то же (find→create) и **больше нигде не вызывается — мёртвый дубликат**;
- `test_read_clients.py` мокает `operations._call_backend` — старое место → реальный HTTP → «transport failure» → `ok:false`.

Правильно: удалить мёртвый `operations._create_client`, свести тесты к одному модулю (`client_cards`). Это нарушение правила «Существующих механизмов» (#63) — новую логику написали рядом со старой.

## 6. Известные грабли этого проекта (не повторять)

Повторяющийся failure mode, из-за которого меняется контекст. Все закрываются `engineering-principles` — читать его как рабочий чек-лист, не как фон.

1. **Проектирование поверх существующего.** Были: предложение добавить `exclude_booking_id` (уже реализован автором); `client_cards` дублирует `operations._create_client`; предложение stateful-планировщика вместо диалогового плана. → §4 «Проверка фактов до проектирования» + поле PR «Существующие механизмы».
2. **Ручная правка импортов → круги CI.** Импорты/формат правили руками, каждый раз новая I001. → только `ruff check --fix`, локальное воспроизведение (#78).
3. **Чинили не тот файл.** Правку вносили по догадке, не воспроизведя ошибку; при недоступном DNS — гадание. → diff-инструмент называет файл и строку; воспроизводить локально или запросить ревьюера с checkout.
4. **Контракт-тесты отстают от кода.** После переезда модуля дословные assert'ы падали (skill-фразы; `from .tools` → `.reliable_tools`), а CI-контракты окаменевали на старом состоянии. → при переименовании/переезде и при обновлении handoff синхронно обновлять контракт-тесты; в контрактах якорить структурные инварианты, не волатильные SHA/PR/даты.

## 7. Следующая веха: NAILS-002F

После разбора открытых PR — автоматические бэкапы PostgreSQL + **подтверждённый restore-тест** (restore в отдельную БД, документированный результат). Это **жёсткий барьер**: реальные данные мастера не заводятся до успешного restore-теста. Крупные подсистемы (Google Calendar, публичный бот, multi-master) не начинать, пока мастер не живёт на системе.

Latency (Issue #69): guarded mutation уже схлопывает read→write→readback в один tool-вызов; оптимизация читающей фазы — после замера доли времени модель/tool, не раньше.

## 8. Точка продолжения

```text
1. довести PR #81: удалить мёртвый operations._create_client, свести тесты к client_cards, зелёный pytest
2. по готовности PR — candidate-validation по exact PR-head SHA, затем ff-merge того же SHA (ADR-003)
3. затем NAILS-002F: бэкапы + проверенный restore
```
