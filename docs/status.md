# Фактическое состояние проекта

Дата актуализации: **14 июля 2026 года**.

Для быстрого продолжения в новом контексте сначала читать [`context/current.md`](context/current.md).

## 1. Сводка

| Область | Состояние |
|---|---|
| Production repository | `385a92962e3736553335d717adcdf4b83ac8a8b3`, clean |
| Backend API и PostgreSQL | production, healthy/ready |
| Alembic | `0006` |
| Hermes Telegram gateway | production, active |
| Onboarding plugin | production, enabled, version `0.5.0` |
| Scheduling plugin | production, enabled, version `0.1.0` |
| Scheduling API/actions | реализованы и зарегистрированы |
| Telegram visibility | оба Nails tools видимы |
| Scheduling deployment | завершён успешно через V3 |
| Telegram happy-path acceptance | выполняется вручную, issue #34 открыт |
| Backup/restore automation | ещё не завершена |
| Пилот с мастером | не начат |

## 2. Production identity

```text
hostname: de.funti.cc
repository: /opt/nails/repo
branch: main
HEAD: 385a92962e3736553335d717adcdf4b83ac8a8b3
working tree: clean
backend API: http://127.0.0.1:8210
Alembic: 0006
```

Backend containers:

```text
nails-api — running/healthy
nails-db  — running/healthy
```

Health endpoints:

```text
GET /health — ok
GET /ready  — ready
```

Последний Hermes-only deployment доказал, что `nails-api`, `nails-db` и Docker daemon не были перезапущены или заменены.

## 3. Hermes production

Установка:

```text
Hermes Agent v0.18.2 (2026.7.7.2)
Python 3.11.15
installation root: /usr/local/lib/hermes-agent
profile: /root/.hermes/profiles/nails
config: /root/.hermes/profiles/nails/config.yaml
```

Gateway:

```text
unit: hermes-gateway-nails.service
manager: root user-level systemd
fragment: /root/.config/systemd/user/hermes-gateway-nails.service
state: active
```

Правильное управление:

```bash
XDG_RUNTIME_DIR=/run/user/0 systemctl --user \
  <status|show|stop|start|restart> hermes-gateway-nails.service
```

System-level `systemctl status hermes-gateway-nails.service` для этого gateway неверен.

## 4. Production plugins и Telegram tools

Enabled plugins:

```text
nails-onboarding  version 0.5.0
nails-scheduling version 0.1.0
```

Registered tools/toolsets:

```text
nails_onboarding
nails_scheduling
```

Telegram toolset membership:

```text
clarify
image_gen
nails_onboarding
nails_scheduling
skills
tts
vision
```

Проверено после последнего restart:

```text
PLUGIN_LIST_OK=true
PLUGIN_REGISTRY_OK=true
TELEGRAM_VISIBILITY_OK=true
KEYS_MATCH=true
gateway_error_scan=clean
```

Forbidden broad tools не включались. Generic HTTP, terminal, filesystem, browser, code execution, SQL, SSH, GitHub, deployment и MCP tools не должны становиться model-visible для рабочего Telegram-профиля.

Подробный контракт: [`operations/hermes-plugin-runtime.md`](operations/hermes-plugin-runtime.md).

## 5. Onboarding boundary

Onboarding tool:

```text
nails_onboarding
```

Trusted identity поступает из Hermes session environment, а не из model arguments:

```python
get_session_env("HERMES_SESSION_PLATFORM", "")
get_session_env("HERMES_SESSION_USER_ID", "")
```

Свойства boundary:

- fail closed вне Telegram;
- Telegram user ID не может быть подменён моделью;
- backend URL фиксирован на loopback;
- internal key не показывается модели;
- backend повторно проверяет активного пользователя и роль;
- generic HTTP не выдаётся модели.

Onboarding plugin продолжил работать после добавления scheduling plugin; `plugins.enabled` был расширен, а не заменён.

## 6. Scheduling boundary

Scheduling tool:

```text
nails_scheduling
```

Доступные actions:

```text
list_services
day_view
free_slots
find_client
create_client
create_booking
```

Основные правила:

- identity берётся только из trusted Hermes session;
- URL фиксирован на `http://127.0.0.1:8210`;
- write actions требуют подтверждения;
- exact client lookup выполняется до создания клиентки;
- идемпотентность защищает от повторной записи;
- backend проверяет пересечения, availability, длительность и buffers;
- model-visible schema не содержит Telegram identity или произвольного URL.

## 7. NAILS-002E4 deployment history

### V1 — заблокирован

```text
ops/deploy/nails-002e4.sh
```

Причины:

- неверно использовал system-level systemd;
- ожидал вымышленную comma-separated allowlist вместо structured YAML.

V1 больше не запускать.

### V2 — rollback выполнен

```text
ops/deploy/nails-002e4-v2.sh
attempted release: b529b577fdaed5c8c1cfbcdbe24bce79a419004f
```

До ошибки V2 успешно подтвердил:

```text
CONFIG_UPDATED_ATOMICALLY=true
CONFIG_POSTSTATE_OK=true
PLUGIN_LIST_OK=true
```

Ошибка была в read-only verification:

- `_get_platform_tools` вернул set-like unordered collection;
- runbook ошибочно сравнивал iteration order;
- `discover_plugins(force=True)` создавал duplicate registration warning для built-in provider `basic`.

Rollback доказан:

```text
ROLLBACK_PERFORMED=true
ROLLBACK_HEAD_CURRENT=5565a524b75a04fe5d8bc2c3e758d2994e9d9c12
ROLLBACK_GATEWAY_STATE=active
```

Полный отчёт: [`deployments/2026-07-13-nails-002e4-v2-rollback.md`](deployments/2026-07-13-nails-002e4-v2-rollback.md).

V2 больше не запускать.

### V3 — production success

```text
runbook: ops/deploy/nails-002e4-v3.sh
release: 385a92962e3736553335d717adcdf4b83ac8a8b3
success marker: NAILS_002E4_V3_DEPLOYMENT_OK
backup: /root/.hermes/profiles/nails/backups/nails-002e4-v3-20260713T215800Z
```

V3 исправил verification:

- `discover_plugins()` вызывается без `force=True`;
- toolsets сравниваются как множество по exact membership;
- сортировка используется только там, где нужен deterministic list;
- assertion показывает observed value.

Production result:

```text
plugins_enabled=nails-onboarding,nails-scheduling
plugin_source_target_match=true
skill_source_target_match=true
runtime_release_files_only=true
gateway_state=active
backend_api_container_unchanged=true
backend_db_container_unchanged=true
docker_daemon_unchanged=true
migration_executed=false
database_write_executed=false
backend_restart_executed=false
rollback_performed=false
```

`gateway_stop_state=failed` во время controlled stop был принят только при `MainPID=0`; последующий start вернул unit в `active/running` с новым положительным PID.

## 8. Активная задача

```text
Issue #34 — NAILS-002E4: Restricted Hermes scheduling tool и Telegram happy path
```

Deployment-часть завершена. Issue остаётся открытым до ручной Telegram-приёмки и финальной read-only production-проверки.

## 9. Acceptance fixture

Услуги:

```text
Маникюр: 2500 RUB, 120 минут, after buffer 21 минута
Педикюр: 2800 RUB, 100 минут, after buffer 20 минут
```

Availability:

```text
2026-07-14 11:00–20:00
2026-07-15 11:00–20:00
2026-07-18 11:00–15:00
```

Последнее известное состояние перед ручной проверкой:

```text
clients: 0
bookings: 0
```

18 июля 2026 года — суббота. Для маникюра последний допустимый старт — `12:30`, резерв заканчивается в `14:51`. Старт `13:00` недопустим, потому что резерв закончился бы в `15:21`.

## 10. Текущая точка ручной приёмки

Пользователь должен отправить боту ровно одно сообщение:

```text
Что у меня 18 июля?
```

Ожидается:

- один breadcrumb `Думаю… (nails_scheduling)`;
- суббота, 18 июля 2026 года;
- availability `11:00–15:00`;
- записей нет.

После фактического ответа нужно остановиться, сравнить его с критериями и только затем переходить к следующему сообщению.

Полная последовательность acceptance находится в [`context/current.md`](context/current.md).

## 11. Что осталось по issue #34

1. Проверить day view.
2. Проверить free slots для маникюра: `11:00`–`12:30` каждые 15 минут.
3. Проверить exact lookup и подтверждаемое создание клиентки Анны.
4. Создать booking на `18 июля 12:30` только после явного подтверждения.
5. Проверить отсутствие дубля при повторе.
6. Проверить отклонение `13:00`.
7. Проверить overlap rejection.
8. Выполнить отдельный read-only production diagnostic по итоговым counts и логам.
9. Зафиксировать результаты в GitHub.
10. Закрыть issue #34 только после всех проверок.

## 12. Следующие продуктовые этапы

После NAILS-002E4:

- перенос и отмена записей;
- личные блоки времени;
- более полный клиентский профиль и приватные заметки;
- утренняя сводка;
- финансовые итоги;
- автоматизированный backup и verified restore;
- ограниченный пилот с мастером после всех safety gates.

## 13. Change process

- код, миграции, тесты и документация меняются через GitHub;
- CI и review обязательны;
- production deployment выполняет VPS-агент по exact merged SHA;
- VPS-агент не редактирует tracked files и не принимает решений;
- ошибки production возвращаются основному агенту как диагностика;
- secrets, Telegram IDs, телефоны и реальные приватные заметки в Git не попадают.
