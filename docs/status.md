# Фактическое состояние проекта

Дата актуализации: **20 сентября 2026 года**.

Перед любым release-решением exact SHA проверяются заново: GitHub `main` — через fresh GitHub preflight, production — через VPS preflight. Этот tracked-файл не является реестром текущего running SHA.

## 1. Сводка

| Область | Состояние |
|---|---|
| GitHub `main` на момент актуализации | `4ab4e6f80adefad80d03bf5b484d051b974738e1` |
| Последний подтверждённый production deploy | `9b9c4829dfc6595441421a9d3c8fc2f6a53120af` |
| Production host | `de.funti.cc` |
| Master web | `https://de.funti.cc:8446/web/` |
| Alembic head в `main` | `0025` |
| Master Telegram | Hermes profile `nails` |
| Client Telegram | отдельный deterministic runtime, один платформенный bot |
| Client runtime lifecycle | встроен в штатный `compose.yaml` / `ops/deploy/deploy.sh` |
| Multi-master client binding | реализован по ADR-009 |
| Master cabinet | календарь, клиентки, прайс, статистика, заявки клиенток, профиль/настройки |
| Backup/restore | ежедневный backup, retention, restore-contract, backup перед deploy |
| Production application/runtime | последний подтверждённый runtime = `9b9c482...`; exact state проверять preflight |
| Alembic | `0025` в текущем `main` |
| Active issue | #323 mobile acceptance; остальные реальные open scope ниже |
| Текущий этап | mobile UX/acceptance и эксплуатационная доводка |
| Текущий product context | `docs/context/current.md` |

## 2. Что фактически реализовано

### Контур мастера

- onboarding и постоянные настройки мастера;
- обычные рабочие часы и исключения по конкретным датам;
- несколько интервалов в день и целый выходной;
- «Мой прайс»: base/addon, fixed/range/per-unit/on-request, архив/восстановление;
- клиентские карточки, внутренние заметки и поиск;
- создание, перенос, мягкая отмена и финализация записи;
- проверка overlap/day-off и snapshots состава, цены и длительности;
- календарь день/неделя/месяц;
- статистика и XLSX/CSV выгрузки;
- Telegram-подтверждение входа в web-кабинет;
- account menu: профиль для клиенток, настройки, выход;
- входящие заявки клиенток с resolve/link/create, approve/reject;
- итоговая цена и редактирование записи в кабинете.

### Клиентский Telegram-контур

Реализован не как будущий план, а как рабочий код:

- отдельный deterministic Telegram bot без Hermes/LLM;
- один платформенный bot обслуживает нескольких мастеров;
- deep-link/start-token резолвит мастера **только сервер**;
- `owner_user_id` нельзя выбирать через client body/query;
- `master_public_profile` с обязательным `display_name`;
- `public_contact` только explicit opt-in;
- multi-binding: одна Telegram-клиентка может быть связана с несколькими мастерами;
- «Ваши мастера» строится только по существующим binding'ам, без публичного каталога;
- публичный прайс и свободные окна;
- server-side booking draft с TTL;
- выбор base service, addons и quantities;
- пересчёт состава, цены и длительности на сервере;
- отправка `BookingRequest`, которая **не резервирует слот**;
- master approve повторно проверяет фактический overlap/day-off и создаёт обычный Booking;
- reject и conflict не выполняют скрытый автоперенос;
- «Мои записи»/актуальные заявки в клиентском интерфейсе;
- короткое пояснение/сообщение мастеру как информация, а не команда бизнес-логики;
- outbox транзакционных уведомлений и отдельный drainer;
- уведомления клиентке о подтверждении/отказе;
- reachability/linking и one-time personal links;
- общий invite link мастера и персональная ссылка на карточку;
- отдельные client credentials;
- client API и bot flags разрешены только парой `false/false` или `true/true`;
- штатный deploy проверяет раздельность master/client Telegram token и singleton runtime.

### Приватность клиентского контура

- числовой Telegram ID мастера клиентке не раскрывается;
- личное Telegram-имя/username мастера автоматически не публикуются;
- `@username` виден только если мастер сам записал его в `public_contact`;
- internal aliases, notes и технические идентификаторы не входят в публичную проекцию;
- совпадение имени/телефона не связывает клиентку с существующей карточкой автоматически;
- первую связь подтверждает мастер.

## 3. Архитектурные решения SaaS

ADR-009 принят и реализован в клиентском binding-контуре:

1. один платформенный клиентский bot;
2. server-side start-token → owner;
3. multi-binding;
4. public profile мастера;
5. без публичного каталога мастеров;
6. без per-master white-label bots;
7. billing/subscriptions остаются отдельным будущим этапом.

Старый single-master подход с `CLIENT_OWNER_TELEGRAM_USER_ID` считается obsolete и не должен возвращаться.

## 4. Production и GitHub

Последний подтверждённый production deploy:

```text
sha=9b9c4829dfc6595441421a9d3c8fc2f6a53120af
prev_sha=3817dc211e521b44614ee50169b42a5813434042
running_web_sha=9b9c4829dfc6595441421a9d3c8fc2f6a53120af
running_client_bot_sha=9b9c4829dfc6595441421a9d3c8fc2f6a53120af
client_bot_singleton=true
```

В `main` после этого смержен `4ab4e6f...` с исправлением узкой mobile navigation и recoverable invite flow. Его нельзя считать production без отдельного VPS deploy/preflight.

## 5. Что больше не является «следующим этапом»

Устаревшие формулировки о том, что client runtime, client identity, booking requests или multi-master ещё только предстоит сделать, больше не соответствуют коду `main`.

## 6. Текущая работа

Активными остаются только реально незавершённые или не принятые задачи, в частности:

- #323 — mobile UI acceptance заявок/confirm dialog/profile placement;
- #316 — механическая защита `main` от direct push;
- #268 — накопленный cabinet UX debt;
- #282 — полноценная недельная модель редактирования графика в кабинете ещё не закрыта: сейчас есть общий рабочий интервал + исключения по датам;
- #284 — прозрачность всех факторов, ограничивающих client slots, требует отдельной финальной acceptance;
- #252 — устранение global render overrides/script-order coupling;
- #223 — будущая автоматизированная воронка подключения мастеров.
