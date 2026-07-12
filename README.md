# Nails — Telegram-помощник мастера по записи

Nails создаётся как закрытый помощник мастера в Telegram. В целевой версии ему можно будет писать обычными словами:

> Что у меня завтра?

> Покажи свободное время в пятницу после 16:00.

> Подготовь запись новой клиентки на маникюр с покрытием.

> В воскресенье не работаю, закрой весь день.

Помощник будет учитывать график, длительность услуг, буферы, существующие записи и подтверждения мастера. PostgreSQL остаётся единственным источником истины, а модель не получает прямой доступ к серверу или базе данных.

## Текущий статус

На 13 июля 2026 года `NAILS-002B` завершён и работает в production на `de.funti.cc`. Код `NAILS-002C` реализован в PR #14 и ожидает полного CI, merge и отдельного production deployment.

### Уже работает в production

- отдельный Telegram-бот и профиль Hermes `nails`;
- Telegram allowlist и раздельные пользовательские sessions;
- `SOUL.md`, запрещающий обещать несуществующие функции;
- whitelist инструментов: `vision`, `image_gen`, `tts`, `skills`, `clarify`;
- отключены terminal, file access, browser, arbitrary HTTP, code execution, cron, delegation, MCP и встроенная общая память Hermes;
- FastAPI backend и PostgreSQL в изолированном Docker Compose;
- Alembic `0002 (head)`;
- защищённый onboarding API;
- проверка active user и роли `master/admin`;
- start/get/pause/resume/complete onboarding;
- draft и confirmed payload для графика, услуг, буферов и записей наперёд;
- revision tracking и идемпотентные confirmations;
- безопасный audit без полного рабочего payload;
- `/health` и `/ready`;
- restricted DB role `nails_app`;
- API только на `127.0.0.1:8210`, PostgreSQL без host port.

Production commit:

```text
40b25ff5fe519eda8602d0eeac7d06a1b191138d
```

### Реализовано в коде NAILS-002C

- profile-local Hermes plugin `nails-onboarding`;
- один dedicated tool `nails_onboarding`;
- Telegram identity только из trusted task-local context;
- model-visible schema не содержит Telegram ID, URL, headers, request ID или secret;
- backend URL жёстко фиксирован на `127.0.0.1:8210`;
- разрешены только start/get/save/confirm/pause/resume/complete;
- fail-closed для non-Telegram or missing identity;
- одинаковый safe response для backend `401` и `403`;
- ограниченный retry только для transport errors и `502/503/504`;
- обновлён SOUL: draft, confirmed onboarding block и active working data называются по-разному;
- security tests запускаются на Python 3.11 и 3.12.

До merge и production deployment этот tool нельзя считать доступным в Telegram.

### Пока не работает через Telegram

Smart Nails пока не может надёжно:

- сохранять onboarding через production plugin;
- искать реальные свободные окна;
- создавать, переносить или отменять записи;
- рассчитывать рабочую выручку;
- синхронизироваться с Google Calendar.

До production deployment NAILS-002C бот проводит только тестовое интервью и обязан говорить, что сохранение из Telegram ещё не подключено.

## Активный этап: NAILS-002C

После зелёного CI необходимо:

1. Смержить PR #14.
2. Установить plugin только в profile `nails`.
3. Передать authentication setting в profile environment без вывода значения.
4. Добавить только toolset `nails_onboarding` к Telegram whitelist.
5. Проверить identity spoofing, two-user isolation и safe refusal.
6. Проверить pause/resume после restart gateway.
7. Очистить synthetic data.

Issue: [`NAILS-002C`](https://github.com/michailr1/Nails/issues/5).

## Целевая архитектура

```text
Telegram
   ↓
Hermes Telegram Gateway
   ↓ trusted Telegram context
profile: nails
   ↓ restricted domain tools
Booking API (FastAPI)
   ↓
PostgreSQL
```

Hermes отвечает за диалог, но не является источником бизнес-данных. Booking API проверяет роли и правила, а PostgreSQL хранит подтверждённое состояние.

## Роли

- `master` — ведёт собственный график, клиентов и записи;
- `admin` — имеет права мастера и дополнительные административные функции;
- Telegram allowlist разрешает диалог, но не заменяет проверку роли в Booking API;
- `nails_app` — ограниченная техническая роль PostgreSQL;
- `nails_admin` — bootstrap-роль контейнера базы, не используется приложением.

## Защита данных

- реальные имена, телефоны и записи не хранятся в GitHub;
- внутренние обозначения мастера отделяются от публичного имени клиентки;
- внутренние алиасы и заметки не должны попадать в клиентские сообщения;
- важные изменения выполняются только после подтверждения;
- профиль Hermes не имеет shell, SSH, прямого SQL и секретов других профилей;
- production `.env` хранится вне репозитория с правами `600`;
- authentication setting не попадает в prompt, ответы и логи;
- backup и проверка восстановления обязательны до пилота с реальными данными.

## Документация

- [Фактическое состояние проекта](docs/status.md)
- [Restricted Hermes onboarding tool](docs/hermes-onboarding-plugin.md)
- [Отчёт deployment NAILS-002B](docs/deployments/2026-07-13-nails-002b.md)
- [Onboarding API](docs/onboarding-api.md)
- [Архитектура](docs/architecture.md)
- [Бизнес-процессы](docs/business-processes.md)
- [Роли и полномочия](docs/roles-and-permissions.md)
- [Приватность и модель данных](docs/privacy-and-data-model.md)
- [План разработки](docs/roadmap.md)
- [Развёртывание](docs/deployment.md)
- [ADR-002: стек и развёртывание](docs/decisions/ADR-002-technology-and-deployment.md)

## Правило разработки и развёртывания

Код, миграции, CI и документация изменяются через GitHub. VPS-агент на `de.funti.cc` получает готовый `main`, создаёт backup, разворачивает точный commit и выполняет production-проверки. Исправления непосредственно на VPS запрещены.
