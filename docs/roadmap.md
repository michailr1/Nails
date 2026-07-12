# Roadmap

Дата актуализации: **13 июля 2026 года**.

План построен вертикальными срезами. Каждый рабочий срез должен завершаться проверяемой функцией, а не только набором внутренних компонентов.

## Статусы

- ✅ завершено и проверено;
- 🟡 частично выполнено;
- ▶️ следующий активный срез;
- ⬜ запланировано.

## Текущая точка

```text
NAILS-001  🟡 базовые правила согласованы
NAILS-002A ✅ backend foundation в production
NAILS-002B ▶️ onboarding API — следующий этап
NAILS-002C 🟡 Telegram/profile foundation готов, API integration впереди
NAILS-002D 🟡 SOUL готов, production onboarding skill впереди
NAILS-002E ⬜ scheduling happy path
NAILS-002F ⬜ backup и restore-test
```

Production backend работает на `de.funti.cc`, commit:

```text
cca0109ea8c716fdf03d97c34a1c0f06bfb5fc50
```

Подробное фактическое состояние: [`status.md`](status.md).

## NAILS-001 — фиксация процессов и правил 🟡

Базовые решения, достаточные для начала реализации, зафиксированы:

- роли `master` и `admin`;
- PostgreSQL как источник истины;
- разделение публичных и внутренних полей;
- снимок стоимости записи;
- обязательный IANA timezone;
- подтверждение опасных операций;
- backup и restore-test как условие пилота;
- Google Calendar как необязательный односторонний экспорт;
- запрет прямого SQL и shell для Hermes.

Остаётся закрыть финальный чек-лист issue #1 и синхронизировать конкретные бизнес-правила после первого рабочего onboarding.

## NAILS-002 — сквозной happy path

Цель: мастер знакомится с ботом, проходит возобновляемое интервью, создаёт минимальную клиентскую карточку, спрашивает окна, создаёт тестовую запись и видит день.

### NAILS-002A — каркас backend ✅

Завершено и развёрнуто в production:

- Python 3.12 + FastAPI;
- SQLAlchemy 2 + Alembic;
- PostgreSQL 17;
- Pydantic Settings;
- обязательный `APP_TIMEZONE` без fallback;
- Ruff и pytest;
- Docker Compose deployment;
- `/health` и `/ready`;
- initial migration `0001`;
- таблицы:
  - `users`;
  - `services`;
  - `clients`;
  - `bookings`;
  - `schedule_rules`;
  - `schedule_exceptions`;
  - `audit_events`;
  - `onboarding_states`;
  - `onboarding_drafts`;
- owner scoping через `owner_user_id`;
- ограниченная PostgreSQL-role `nails_app`;
- CI: lint, tests, clean migration, repeated migration, Compose smoke-test;
- production deployment на `de.funti.cc`.

Issue #3 закрыта.

### NAILS-002B — onboarding API ▶️

Следующий активный срез.

Объём:

- trusted user identity contract;
- `start_onboarding`;
- `get_onboarding_state`;
- сохранение draft графика;
- сохранение draft услуг, цен и длительностей;
- сохранение draft буферов;
- сохранение draft будущих записей;
- исправление и подтверждение каждого блока;
- `pause_onboarding`;
- `resume_onboarding`;
- `complete_onboarding`;
- audit confirmations and corrections;
- owner and role checks;
- idempotent operations;
- тест продолжения после рестарта API.

Правило: draft не участвует в рабочем расписании до подтверждения соответствующего блока.

### NAILS-002C — Hermes Telegram Gateway и профиль 🟡

Уже выполнено:

- отдельный Telegram bot token;
- отдельный профиль Hermes `nails`;
- отдельный allowlist;
- отдельные пользовательские sessions;
- установлен SOUL;
- профиль отвечает основному и тестовому allowlisted users;
- Telegram whitelist tools:
  - `vision`;
  - `image_gen`;
  - `tts`;
  - `skills`;
  - `clarify`;
- terminal, files, code execution, web/browser, cron, delegation, MCP и infrastructure tools отключены;
- built-in memory и user profile отключены;
- `skills.write_approval=true`.

Остаётся:

- определить контракт trusted Telegram context для domain tools;
- подключить только onboarding/scheduling API tools;
- проверять `master/admin` в Booking API;
- выполнить negative role tests;
- исключить disclosure для запрещённого пользователя.

### NAILS-002D — skill `nails-onboarding` 🟡

Уже выполнено:

- создан и установлен профильный `SOUL.md`;
- бот обязан честно разделять тестовое интервью и рабочее сохранение;
- запрещены заявления о сохранении без успеха API;
- запрещено обещать свободные окна и операции записи до реализации backend functions.

Остаётся:

- создать production skill `nails-onboarding`;
- подключить его к ограниченным NAILS-002B tools;
- знакомство и ответы на вопросы;
- interview flow: график → услуги → буферы → записи;
- короткие возобновляемые sessions;
- summary/confirmation каждого блока;
- capability flags;
- protected feedback logging.

### NAILS-002E — первый scheduling happy path ⬜

- создание минимального клиента с обязательным `public_name`;
- точный поиск по нормализованному публичному имени;
- поиск свободных окон;
- создание записи со snapshot стоимости и валюты;
- overlap prevention;
- компактный просмотр дня;
- skill `nails-scheduling` с узкими API tools;
- контрольные запросы:
  - «что у меня в четверг?»;
  - «какие окна завтра?»;
  - создание синтетической записи.

### NAILS-002F — backup и восстановление ⬜

- автоматические PostgreSQL backups;
- копия вне рабочей базы и вне единственного диска VPS;
- журнал успешности и ошибок;
- test restore в отдельную БД;
- документированный результат восстановления;
- запрет пилота с реальными данными без успешного restore-test.

### Контрольная точка NAILS-002

NAILS-002 считается завершённым, когда:

- полный onboarding пройден ролью `admin`;
- подтверждённые данные сохраняются и переживают restart;
- запрос расписания использует только что подтверждённые данные;
- overlap блокируется backend;
- Hermes не имеет shell, SSH, direct SQL, arbitrary HTTP и чужих secrets;
- roles and ownership проверяются Booking API;
- backup реально восстановлен;
- synthetic data очищены;
- мастер может быть приглашён в ограниченный пилот.

## NAILS-003 — управление записями ⬜

- переносы и отмены;
- time blocks: interval/day/date range;
- подтверждение опасных операций;
- idempotency repeated requests;
- delay handling без автоматического сдвига следующих записей;
- просмотр недели и произвольного периода;
- feedback retention and deletion.

## NAILS-004 — расширенная клиентская база ⬜

- internal aliases and notes;
- exact and fuzzy search;
- typo detection;
- duplicate warning;
- separate public name confirmation;
- `client_service_overrides`;
- персональная длительность и цена;
- полноценный merge дублей остаётся вне MVP.

## NAILS-005 — повседневные сценарии ⬜

- «записать как обычно»;
- `no_show`;
- утренняя сводка;
- завершение визита;
- фиксация фактической цены;
- day/week revenue by price snapshots;
- pilot metrics.

## NAILS-006 — Google Calendar ⬜

- отдельный календарь;
- isolated credentials;
- `calendar_sync_jobs`;
- one-way export;
- retries/backoff;
- reconciliation;
- календарная ошибка не блокирует business operation.

## NAILS-007 — расширенное тестирование ⬜

- double booking;
- occupied transfer;
- ambiguous names;
- same public names;
- internal alias privacy;
- repeated confirmation;
- role isolation;
- owner isolation;
- end-of-day boundaries;
- overnight blocks;
- DST transitions;
- historical price invariance;
- no-show accounting;
- delay conflicts;
- feedback expiry;
- calendar failure isolation;
- verified restore.

## NAILS-008 — пилот ⬜

- parallel old/new schedule;
- reconciliation;
- feedback review;
- pilot metrics;
- service duration corrections;
- backup monitoring;
- переход на основное использование только после явного доверия мастера.

## После MVP

- отдельный public client bot;
- самостоятельная запись клиенток;
- consultation by services and prices;
- mandatory master confirmation;
- separate isolation and abuse protection;
- administrative duplicate merge;
- multi-master subscription product and tenant management.

## Порядок выполнения ближайших задач

1. NAILS-002B — onboarding API.
2. Завершение NAILS-002C — restricted Hermes API tools and roles.
3. Завершение NAILS-002D — production onboarding skill.
4. NAILS-002E — scheduling happy path.
5. NAILS-002F — backup/restore.
6. Full synthetic end-to-end test.
7. Cleanup test data.
8. Limited master pilot.
