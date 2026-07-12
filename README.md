# Nails — Telegram-помощник мастера по записи

Nails создаётся как закрытый помощник мастера в Telegram. В целевой версии ему можно будет писать обычными словами:

> Что у меня завтра?

> Покажи свободное время в пятницу после 16:00.

> Подготовь запись новой клиентки на маникюр с покрытием.

> В воскресенье не работаю, закрой весь день.

Помощник будет учитывать график, длительность услуг, буферы, существующие записи и подтверждения мастера. PostgreSQL остаётся единственным источником истины, а модель не получает прямой доступ к серверу или базе данных.

## Текущий статус

На 13 июля 2026 года код проекта завершает `NAILS-002B`. Production пока остаётся на `NAILS-002A` до отдельного безопасного deployment на `de.funti.cc`.

### Уже работает в production

- отдельный Telegram-бот и отдельный профиль Hermes `nails`;
- Telegram allowlist и раздельные пользовательские сессии;
- системные инструкции Smart Nails, запрещающие обещать несуществующие функции;
- безопасный whitelist инструментов: `vision`, `image_gen`, `tts`, `skills`, `clarify`;
- отключены terminal, file access, browser, arbitrary HTTP, code execution, cron, delegation, MCP и встроенная общая память Hermes;
- FastAPI backend и PostgreSQL в изолированном Docker Compose;
- миграция Alembic `0001`;
- таблицы пользователей, услуг, клиентов, записей, графика, аудита и состояния onboarding;
- `/health` и `/ready`;
- отдельный ограниченный пользователь БД `nails_app`;
- API доступен только на `127.0.0.1:8210`, PostgreSQL не публикует порт наружу.

Production commit базового backend:

```text
cca0109ea8c716fdf03d97c34a1c0f06bfb5fc50
```

### Реализовано в коде NAILS-002B

- защищённый onboarding API;
- trusted Telegram identity contract для будущего Hermes domain tool;
- проверка активного пользователя и роли `master/admin` в PostgreSQL;
- start/get/pause/resume/complete onboarding;
- отдельные draft и confirmed payload для графика, услуг, буферов и записей наперёд;
- revision tracking и идемпотентное подтверждение;
- безопасная инвалидизация зависимых подтверждений;
- audit без сохранения полного рабочего payload;
- Alembic migration `0002`;
- тест продолжения paused onboarding после рестарта API.

До production deployment этот функционал нельзя считать доступным на `de.funti.cc`.

### Пока не работает через Telegram

Smart Nails пока не может надёжно:

- сохранять график, услуги и записи из Telegram;
- вызывать onboarding API через ограниченный Hermes tool;
- искать реальные свободные окна;
- создавать, переносить или отменять записи;
- рассчитывать рабочую выручку;
- синхронизироваться с Google Calendar.

До подключения Booking API к Hermes бот может проводить только тестовое интервью, помогать подготовить данные в текущем диалоге, читать изображения и создавать контент. Он обязан прямо говорить, что рабочее сохранение из Telegram ещё не подключено.

## Ближайшие шаги

1. Развернуть NAILS-002B на `de.funti.cc` и применить migration `0002`.
2. Проверить полный синтетический lifecycle onboarding и очистить тестовые данные.
3. Завершить `NAILS-002C`: подключить к Hermes только узкий onboarding domain tool.
4. Реализовать production skill `nails-onboarding` в `NAILS-002D`.
5. Реализовать первый scheduling happy path в `NAILS-002E`.
6. Настроить backup и реальный restore-test в `NAILS-002F`.
7. Только после этого приглашать мастера в ограниченный пилот.

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
- `admin` — имеет права мастера и дополнительно управляет ролями, настройками и диагностикой;
- Telegram allowlist разрешает начать диалог, но не заменяет проверку роли в Booking API;
- `nails_app` — ограниченная техническая роль PostgreSQL;
- `nails_admin` — bootstrap-роль контейнера базы, не используется приложением.

## Защита данных

- реальные имена, телефоны и записи не хранятся в GitHub;
- внутренние обозначения мастера отделяются от публичного имени клиентки;
- внутренние алиасы и заметки никогда не должны попадать в клиентские сообщения;
- важные изменения выполняются только после подтверждения;
- профиль Hermes не имеет shell, SSH, прямого SQL и секретов других профилей;
- production `.env` хранится вне репозитория с правами `600`;
- `INTERNAL_API_KEY` хранится только в production environment и будущем Hermes domain tool;
- backup и проверка восстановления обязательны до пилота с реальными данными.

## Документация

- [Фактическое состояние проекта](docs/status.md)
- [Onboarding API](docs/onboarding-api.md)
- [Архитектура](docs/architecture.md)
- [Бизнес-процессы](docs/business-processes.md)
- [Роли и полномочия](docs/roles-and-permissions.md)
- [Приватность и модель данных](docs/privacy-and-data-model.md)
- [План разработки](docs/roadmap.md)
- [Развёртывание](docs/deployment.md)
- [ADR-002: стек и развёртывание](docs/decisions/ADR-002-technology-and-deployment.md)
- [Ревью проекта от 2026-07-12](docs/reviews/2026-07-12-project-review.md)

## Правило разработки и развёртывания

Код, миграции, CI и документация изменяются через GitHub. VPS-агент на `de.funti.cc` только получает готовый `main`, разворачивает его и выполняет production-проверки. Исправления непосредственно на VPS запрещены.
