# Nails — текущий контекст для продолжения работы

Дата фиксации: **14 июля 2026 года**.

Этот файл — первая точка входа для нового контекстного окна. Он содержит только актуальное состояние, принятые решения, обнаруженные production-особенности и ближайшие действия. Исторические подробности остаются в связанных документах.

## 1. Рабочий контракт

Репозиторий:

```text
michailr1/Nails
```

Production:

```text
hostname: de.funti.cc
repository: /opt/nails/repo
backend environment: /opt/nails/.env
backend API: http://127.0.0.1:8210
Hermes profile: /root/.hermes/profiles/nails
Hermes config: /root/.hermes/profiles/nails/config.yaml
```

Ветка разработки и production checkout:

```text
main
```

Разделение ответственности неизменно:

- основной агент ChatGPT анализирует, пишет код, меняет GitHub, создаёт PR, проверяет CI и принимает решения;
- VPS-агент только выполняет точный merged runbook и возвращает отчёт;
- VPS-агент не пишет код, не меняет GitHub, не импровизирует и останавливается при ошибке;
- один живой Telegram-тест выполняется за раз.

Обязательное чтение перед работой:

1. [`../../AGENTS.md`](../../AGENTS.md);
2. этот файл;
3. [`../operations/production-infrastructure.md`](../operations/production-infrastructure.md);
4. [`../operations/hermes-plugin-runtime.md`](../operations/hermes-plugin-runtime.md);
5. [`../status.md`](../status.md).

## 2. Текущее production-состояние

Успешно установлен release:

```text
production HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3
working tree: clean
Alembic: 0006
```

Последний успешный runbook:

```text
ops/deploy/nails-002e4-v3.sh
success marker: NAILS_002E4_V3_DEPLOYMENT_OK
```

Production backup этой установки:

```text
/root/.hermes/profiles/nails/backups/nails-002e4-v3-20260713T215800Z
```

Gateway:

```text
service manager: root user-level systemd
unit: hermes-gateway-nails.service
fragment: /root/.config/systemd/user/hermes-gateway-nails.service
state after deployment: active
PID before: 2308856
PID after: 2318431
```

Backend во время Hermes-only deployment не менялся:

```text
nails-api container unchanged: true
nails-db container unchanged: true
Docker daemon unchanged: true
health: ok
ready: ok
migration executed: false
database write executed by deployment: false
backend restart executed: false
```

## 3. Hermes runtime и plugins

Установленный Hermes:

```text
Hermes Agent v0.18.2 (2026.7.7.2)
upstream c44de998
local af250d84 (+1 carried commit)
Python 3.11.15
```

Активные profile-local plugins:

```text
nails-onboarding  0.5.0  -> tool/toolset nails_onboarding
nails-scheduling 0.1.0  -> tool/toolset nails_scheduling
```

Текущий semantic config:

```yaml
plugins:
  enabled:
    - nails-onboarding
    - nails-scheduling
  disabled: []
  entries:
    nails-onboarding:
      allow_tool_override: false

platform_toolsets:
  telegram:
    - vision
    - image_gen
    - tts
    - skills
    - clarify
    - nails_onboarding
    - nails_scheduling
```

Проверено в production:

```text
PLUGIN_LIST_OK=true
PLUGIN_REGISTRY_OK=true
TELEGRAM_VISIBILITY_OK=true
KEYS_MATCH=true
plugin_discovery=idempotent
plugin_registry=ok
telegram_visibility=ok
gateway_error_scan=clean
```

Нулевое число строк `nails_onboarding` или `nails_scheduling` в коротком startup-log не является ошибкой, если plugin list, registry и Telegram definitions проверены успешно.

## 4. С чем столкнулись и как решили

### Попытка V1 — неверная production-топология

Заблокированный файл:

```text
ops/deploy/nails-002e4.sh
```

Проблемы:

1. runbook обращался к system-level systemd, но gateway управляется root user-level systemd;
2. runbook искал вымышленную строковую comma-separated allowlist, хотя config является structured YAML.

Решение:

- использовать только `XDG_RUNTIME_DIR=/run/user/0 systemctl --user ...`;
- парсить YAML, проверять exact pre-state, делать atomic replace и проверять post-state;
- V1 никогда больше не запускать.

### Попытка V2 — ошибка только в read-only verification

Заблокированный файл:

```text
ops/deploy/nails-002e4-v2.sh
```

V2 успел успешно пройти:

```text
CONFIG_UPDATED_ATOMICALLY=true
CONFIG_POSTSTATE_OK=true
PLUGIN_LIST_OK=true
```

Затем read-only Python-проверка упала по двум причинам:

1. `_get_platform_tools(config, "telegram")` в Hermes `v0.18.2` возвращает set-like unordered collection, а V2 сравнивал его с fixed-order list;
2. `discover_plugins(force=True)` повторно пытался зарегистрировать встроенный dashboard-auth provider `basic`, создавая шумное сообщение о duplicate registration.

Важно: сообщение про `basic` не означало поломку `nails-scheduling`; непосредственным падением было сравнение порядка Telegram toolsets.

Rollback V2 прошёл полностью:

```text
ROLLBACK_PERFORMED=true
ROLLBACK_TARGET_HEAD=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_HEAD_CURRENT=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_GATEWAY_STATE=active
```

Полный отчёт:

[`../deployments/2026-07-13-nails-002e4-v2-rollback.md`](../deployments/2026-07-13-nails-002e4-v2-rollback.md).

### V3 — успешное решение

V3 исправил verification:

- вызывает `discover_plugins()` без `force=True`;
- сравнивает Telegram toolsets как множество по exact membership;
- сортирует toolsets только при передаче в `get_tool_definitions`;
- показывает observed values при assertion failure;
- сохраняет backup, rollback и изоляцию backend/Docker.

Особенность остановки gateway:

```text
gateway_stop_state=failed
```

Это допустимо в этом runbook только вместе с `MainPID=0`: сервис остановлен, а после старта обязан вернуться в `active/running` с новым положительным PID. Финальная проверка это подтвердила.

## 5. Текущая задача

Активная задача:

```text
Issue #34 — NAILS-002E4: Restricted Hermes scheduling tool и Telegram happy path
```

Deployment завершён. Issue нельзя закрывать до ручной Telegram-приёмки и финальной read-only production-проверки.

Реализованные scheduling actions:

```text
list_services
day_view
free_slots
find_client
create_client
create_booking
```

Все write actions требуют подтверждения. Trusted Telegram identity берётся из Hermes session environment и не передаётся моделью.

## 6. Acceptance fixture

Последнее подготовленное состояние для ручной проверки:

Услуги:

```text
Маникюр: 2500 RUB, 120 минут, after buffer 21 минута
Педикюр: 2800 RUB, 100 минут, after buffer 20 минут
```

Доступность:

```text
2026-07-14 11:00–20:00
2026-07-15 11:00–20:00
2026-07-18 11:00–15:00
```

Последнее известное состояние до ручной приёмки:

```text
clients: 0
bookings: 0
```

18 июля 2026 года — суббота (`weekday_iso=6`).

Для маникюра 18 июля:

```text
последний допустимый старт: 12:30
резерв до: 14:51
13:00 недопустимо
резерв при 13:00 был бы до: 15:21
```

## 7. Ручная Telegram-приёмка — строго по одному сообщению

### Шаг 1 — day view

Отправить:

```text
Что у меня 18 июля?
```

Ожидать:

- ровно один breadcrumb `Думаю… (nails_scheduling)`;
- суббота, 18 июля 2026 года;
- рабочее время `11:00–15:00`;
- записей нет.

После ответа остановиться и зафиксировать фактический текст/скриншот.

### Шаг 2 — free slots

Только после принятия шага 1 отправить:

```text
Какие окна 18 июля на маникюр?
```

Ожидать старты каждые 15 минут:

```text
11:00, 11:15, 11:30, 11:45,
12:00, 12:15, 12:30
```

Не должно быть `12:45` или `13:00`.

### Шаг 3 — клиентка и запись

Отправить:

```text
Запиши Анну на маникюр 18 июля в 12:30.
```

Ожидать:

1. exact client lookup;
2. если клиентки нет — вопрос, новая ли это клиентка или опечатка;
3. создание клиентки только после подтверждения;
4. показ итогов записи;
5. создание booking только после отдельного явного подтверждения.

### Шаг 4 — idempotency

Повтор той же команды не должен создать вторую клиентку или вторую запись.

### Шаг 5 — позднее время

Попытка записать маникюр на `13:00` должна быть отклонена, потому что услуга с buffer выходит за `15:00`.

### Шаг 6 — overlap

Попытка создать пересекающуюся запись должна быть отклонена без изменения существующей записи.

### Шаг 7 — финальная production-проверка

После пользовательских тестов основной агент готовит отдельный read-only diagnostic runbook для проверки:

- фактического количества clients/bookings;
- отсутствия дублей;
- корректных времён и service IDs;
- отсутствия секретов и лишних персональных данных в логах;
- health/readiness и active gateway.

VPS-агент не должен самостоятельно придумывать SQL или диагностические команды.

## 8. Что не делать

- не повторять deployment: V3 уже установлен;
- не запускать V1 или V2;
- не менять production config вручную;
- не перезапускать backend или Docker для Telegram-приёмки;
- не выполнять несколько Telegram-сценариев одновременно;
- не закрывать issue #34 до всех acceptance steps;
- не считать plugin list или `getMe` заменой реальному Telegram-ответу;
- не публиковать Telegram IDs, телефоны, токены, API keys или реальные приватные заметки.

## 9. Следующее действие

Текущая точка остановки:

```text
пользователь собирается проверить Telegram step 1
```

Следующий агент должен дождаться фактического ответа бота на:

```text
Что у меня 18 июля?
```

Затем сравнить ответ с критериями шага 1 и только после этого дать одно следующее тестовое сообщение.
