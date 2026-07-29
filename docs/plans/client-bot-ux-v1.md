# Client Bot UX v1

Статус: draft product/UX specification

Связано: ADR-004, ADR-009 decisions, Issue #171, PR #240.

## 1. Цель

Зафиксировать клиентский Telegram UX до дальнейшего наращивания bot-кода.

Клиентский бот — отдельный публичный детерминированный интерфейс без LLM. Он помогает клиентке выбрать мастера, посмотреть публичный прайс, собрать состав процедуры, выбрать актуальное свободное время, отправить заявку и управлять только собственными заявками/подтверждёнными записями.

Заявка не является записью и не резервирует время. Обычный Booking появляется только после явного approve мастером через доверенный контур.

## 2. Нормативные принципы

1. Один платформенный клиентский Telegram-бот. Не отдельный бот на каждого мастера.
2. Мастер определяется server-side через start token / существующий binding. `owner_user_id` не приходит из Telegram callback/body.
3. Multi-binding разрешён: одна клиентка может быть связана с несколькими мастерами. Последний выбранный мастер — текущий контекст, но переключение всегда явное.
4. До первой заявки отдельного master gate нет: перешла по ссылке — может смотреть публичные данные и отправлять request.
5. Автопривязки карточки по имени, username или телефону нет.
6. Нет LLM, интерпретации свободного текста и скрытых бизнес-решений на стороне Telegram runtime.
7. Все цены, длительности, состав, доступность и итоговая запись берутся из owner-scoped backend.
8. Callback считается недоверенным вводом: он только указывает, что пользователь хочет выбрать. Перед мутацией серверное состояние перечитывается заново.
9. Pending request не блокирует слот. Перед submit выполняется fresh slot recheck; при approve overlap проверяется ещё раз доменным booking path.
10. В callback нельзя помещать owner id, client id, master Telegram id, цену, имя, телефон или другие персональные/бизнес-данные.

## 3. Тон и визуальная модель

Бот говорит нейтрально, дружелюбно и коротко. Это не «личная помощница мастера» и не имитация человека.

Текст должен объяснять только текущее действие и следующий шаг. Не использовать CRM-терминологию, `binding`, `request`, `service`, `addon`, `owner`, `scheduled` и другие внутренние слова.

Пользовательские сущности:

- мастер;
- прайс;
- процедура;
- дополнение;
- дата;
- время;
- заявка;
- запись.

Правило кнопок:

- основной следующий шаг — первая/самая заметная кнопка;
- destructive action визуально отделён;
- на экране не более одного уровня решения;
- всегда есть понятный возврат, если пользователь находится глубже home;
- не показывать кнопки, которые невозможно выполнить в текущем состоянии.

## 4. Верхнеуровневые состояния UX

```text
cold_start
  -> master_context

master_context
  -> home
  -> master_picker

home
  -> price
  -> booking_service
  -> requests_and_bookings
  -> master_info
  -> master_picker

booking_service
  -> booking_addons
  -> booking_date

booking_addons
  -> booking_date

booking_date
  -> booking_slot

booking_slot
  -> booking_summary

booking_summary
  -> request_sent
  -> booking_service
  -> booking_addons
  -> booking_date
  -> booking_slot

requests_and_bookings
  -> request_details
  -> booking_details

request_details
  -> request_cancelled (pending only)

booking_details
  -> future change-request flows (outside v1 unless separately accepted)
```

UX-state не является источником истины. Его можно восстановить из callback + fresh backend readback.

## 5. `/start` и выбор мастера

### 5.1 Deep-link с валидным start token

Бот вызывает `/api/v1/client/start` и получает owner-scoped binding.

Экран:

```text
Маникюр у Насти

Здесь можно посмотреть прайс и отправить заявку на запись.
```

Кнопки:

```text
📅 Записаться
💅 Прайс
📋 Мои заявки и записи
ℹ️ О мастере
👩‍🎨 Ваши мастера   (только если bindings > 1)
```

Если binding новый, его `pending` статус не показывается клиентке.

### 5.2 `/start` без token

Если существует один binding — открыть home этого мастера.

Если bindings несколько — `master_picker`.

Если bindings нет:

```text
Откройте ссылку мастера, чтобы посмотреть прайс и записаться.
```

Никакого публичного каталога мастеров или поиска.

### 5.3 Master picker

```text
К кому хотите перейти?
```

По одной кнопке на мастера:

```text
Настя
Мария
```

После выбора открывается `home` выбранного binding.

## 6. Home

```text
Настя

Что хотите сделать?
```

Основные кнопки:

```text
📅 Записаться
💅 Прайс
📋 Мои заявки и записи
ℹ️ О мастере
👩‍🎨 Ваши мастера   (при нескольких bindings)
```

Не использовать одновременно «Записаться» и «Выбрать услугу» на home.

## 7. Прайс

Прайс — read-only представление активного owner-scoped каталога.

Группировка по разделам прайса. Для позиции показывать:

- публичное название;
- цену/диапазон/«цена уточняется» согласно catalog semantics;
- ориентировочную длительность, если она публично доступна;
- без внутренних описаний и служебных полей.

Навигация:

```text
📅 Записаться
← Главное меню
```

Если прайс большой, v1 допускает пагинацию/разделы кнопками вместо одного длинного сообщения.

## 8. Booking flow

### 8.1 Выбор процедуры

Экран:

```text
Выберите процедуру
```

Показываются только активные base-позиции. Визуально лучше сначала разделы прайса, если base-позиций много.

Кнопки используют короткий server-resolved индекс/handle, а не имя процедуры.

```text
Маникюр с гель-лаком
Классический маникюр
Педикюр
...
← Главное меню
```

После нажатия backend/catalog перечитывается; индекс разрешается в текущей свежей выборке.

### 8.2 Дополнения

Если для base процедуры нет применимых addon — шаг пропускается.

Экран:

```text
Маникюр с гель-лаком

Добавить что-нибудь?
```

Булевы дополнения:

```text
☐ Снятие · +300 ₽ · +15 мин
☑ Дизайн · +150 ₽
```

Кнопка меняет состояние выбора локально/в короткоживущем server-side flow context, но итог всегда пересчитывается свежим catalog backend.

Количественные дополнения:

```text
Ремонт уголка
−   2   +
```

Количество ограничивается catalog/domain contract. Цена и время масштабируются только по правилам `per_unit` / `time_per_unit`.

Нижние кнопки:

```text
Продолжить
Без дополнений   (если ничего не выбрано)
← К процедурам
```

Не показывать техническое слово «addon».

### 8.3 Выбор даты

Показывать даты, для которых теоретически возможны слоты для выбранного состава.

Базовый v1 может показывать ближайшие 14 дней, но кнопки без доступных окон должны либо отсутствовать, либо быть явно недоступны — не заставлять клиентку проваливаться в пустой день.

Подписи:

```text
Сегодня, 29 июля
Завтра, 30 июля
31 июля
1 августа
```

Для компактной сетки допускается:

```text
29 июл
30 июл
31 июл
1 авг
```

Кнопки:

```text
← К дополнениям / ← К процедуре
```

### 8.4 Выбор времени

Перед отображением вызывается fresh slots для полного выбранного состава.

```text
31 июля
Выберите время
```

Сетка:

```text
11:00   13:30   16:00
18:30   20:00
```

Callback содержит только compact binding handle + service/flow handle + compact timestamp.

Перед переходом к summary слот перечитывается и должен всё ещё быть доступен.

Если слот пропал:

```text
Это время уже заняли. Выберите другое.
```

И сразу показать свежий список времени того же дня, а не выкидывать на начало.

### 8.5 Сводка

Перед показом summary выполнить fresh catalog/composition calculation.

```text
Проверьте заявку

Маникюр с гель-лаком
+ снятие
+ ремонт уголка ×2

31 июля в 16:00
Ориентир по времени: 2 ч 25 мин
Стоимость: 3 350 ₽

После отправки мастер подтвердит заявку.
Пока подтверждения нет, время не забронировано.
```

Если цена `on_request` или диапазон — текст соответствует публичному catalog contract, бот не вычисляет собственную цену.

Кнопки:

```text
Отправить заявку
Изменить время
Изменить процедуру
← Главное меню
```

Если есть addons, допускается отдельная `Изменить дополнения`.

### 8.6 Submit

Перед POST `/api/v1/client/requests`:

1. resolve binding по Telegram identity;
2. fresh catalog composition;
3. fresh slot recheck;
4. сформировать deterministic idempotency key;
5. отправить только разрешённый client request payload.

При успехе:

```text
Заявка отправлена ✨

31 июля в 16:00
Маникюр с гель-лаком

Мастер ещё должен подтвердить запись.
Пока время не забронировано.
```

Кнопки:

```text
📋 Мои заявки и записи
← Главное меню
```

Повторная доставка того же callback не создаёт вторую заявку.

## 9. Мои заявки и записи

Экран должен визуально разделять заявки и записи.

### 9.1 Pending

```text
Ждёт подтверждения
31 июля, 16:00 · Маникюр с гель-лаком
```

Кнопка детали.

В detail:

```text
Заявка ждёт подтверждения мастера.
Время пока не забронировано.
```

Кнопки:

```text
Отменить заявку
← Назад
```

### 9.2 Approved / Booking

После approve сущность показывается как «Запись подтверждена», а не как approved request.

```text
Запись подтверждена ✅
31 июля, 16:00
Маникюр с гель-лаком
```

В v1 не обещать прямой перенос/отмену Booking, пока соответствующий продуктовый контракт не принят. Можно показать фиксированный текст, что изменение записи будет отдельным действием/запросом мастеру.

### 9.3 Rejected

```text
Мастер не смог подтвердить заявку.
Можно выбрать другое время.
```

Кнопки:

```text
Выбрать другое время
📅 Новая заявка
```

Не использовать «Отклонено» как основной пользовательский текст.

### 9.4 Cancelled

```text
Заявка отменена
```

Без destructive actions.

## 10. Ошибки и recovery

### Callback устарел / объект изменился

```text
Данные обновились. Показываю актуальный вариант.
```

Перечитать нужный экран.

### Услуга больше недоступна

```text
Этой процедуры сейчас нет в прайсе. Выберите другую.
```

Вернуть в service picker.

### Дополнение больше недоступно

Удалить его из composition и явно сообщить:

```text
Одно из дополнений больше недоступно. Проверьте состав ещё раз.
```

Вернуть в addons/summary.

### Нет свободных окон

```text
На выбранную дату свободного времени уже нет.
```

Показать другие доступные даты.

### Slot стал занят

```text
Это время уже заняли. Выберите другое.
```

Остаться на slot picker.

### Request conflict/idempotency

Если тот же callback уже успешно создал request — показывать существующий результат как success, а не ошибку.

### API недоступен

```text
Сейчас не получилось загрузить данные. Попробуйте ещё раз чуть позже.
```

Кнопка:

```text
Повторить
```

Не показывать HTTP-коды, traceback и внутренние error codes.

### Revoked binding

Не раскрывать причину:

```text
Эта ссылка больше не действует. Откройте актуальную ссылку мастера.
```

## 11. Back semantics

Back — навигация, не отмена данных.

- из slot -> date;
- date -> addons или service;
- addons -> service;
- service -> home;
- detail -> list;
- master home -> master picker только при multi-binding.

После отправки request Back не должен возвращать пользователя в старый summary с возможностью случайно повторить submit. Использовать idempotency и вести в request details/home.

## 12. Callback contract

### 12.1 Общие требования

- Telegram `callback_data` <= 64 bytes;
- ASCII compact format;
- callback не является авторизацией;
- Telegram user ID берётся из Update transport;
- binding принадлежность проверяется server-side;
- owner определяется только через binding;
- business object разрешается по свежему owner-scoped readback;
- callback не содержит персональных данных.

### 12.2 Допустимые значения

Примеры логической формы, не обязательный wire format:

```text
m:<binding_handle>
h:<binding_handle>
p:<binding_handle>
b:<binding_handle>
s:<binding_handle>:<service_index>
a:<flow_handle>:<addon_index>:<op>
d:<flow_handle>:<yyyymmdd>
t:<flow_handle>:<yyyymmddhhmm>
x:<request_handle>
```

Для сложного composition v1 предпочтителен `flow_handle`, указывающий на короткоживущий server-side draft state, а не попытка сериализовать addons/quantities в callback.

### 12.3 Запрещено

```text
owner_user_id
client_id
master telegram_user_id
client telegram_user_id
phone
public/private name
service/addon raw names
price
auth token/API key
```

## 13. Server-side booking draft для сложного состава

После появления addons callback-only stateless схема становится хрупкой и быстро упирается в 64 bytes.

Рекомендуемый v1 contract: короткоживущий `client_booking_draft`/эквивалент server-side state:

- owner/binding определяется server-side;
- base service handle/index;
- выбранные addon handles и quantities;
- выбранная дата/слот;
- created/updated timestamp;
- короткий opaque flow id для callback;
- TTL допустим только для UX draft и не имеет отношения к reservation/hold слота.

Этот draft не является booking request, не резервирует время и может быть безопасно пересобран из UI.

Перед request submit все catalog references и slot всё равно валидируются заново.

## 14. Responsibility boundaries

### Telegram runtime

Должен:

- принимать Update;
- извлекать verified Telegram user ID;
- маршрутизировать фиксированные commands/callbacks;
- рендерить шаблоны и inline keyboards;
- вызывать client API;
- отвечать callback query;
- выполнять retry transport только в рамках идемпотентного контракта.

Не должен:

- читать БД напрямую;
- выбирать owner самостоятельно;
- вычислять бизнес-цену;
- рассчитывать availability самостоятельно;
- создавать Booking;
- связывать Client;
- принимать решения approve/reject;
- интерпретировать свободный текст через LLM.

### Client API/backend

Отвечает за:

- binding/owner isolation;
- публичный catalog projection;
- composition validation/calculation;
- availability/free slots;
- request lifecycle;
- idempotency;
- audit;
- privacy;
- master approve/reject через trusted contour.

### Master cabinet/trusted contour

Отвечает за:

- увидеть pending заявку;
- явно создать/связать карточку клиентки;
- approve/reject;
- обработать конфликт слота;
- дальнейшие изменения подтверждённой записи согласно master booking contract.

## 15. Что не входит в UX v1

- LLM/чат с клиенткой;
- публичный поиск мастеров;
- отдельные Telegram-боты мастеров;
- скидки/промокоды/рекомендации;
- платежи;
- hold слота;
- автоподтверждение;
- авто-link карточки;
- свободные комментарии как доменные аргументы;
- прямой перенос/отмена подтверждённой записи клиенткой без отдельного решения;
- белый label/custom theme каждого мастера.

## 16. Acceptance UX v1

Спецификация считается реализованной, когда automated/candidate E2E подтверждает:

1. deep-link -> correct master home;
2. multi-binding -> explicit master picker;
3. price -> only public active catalog;
4. booking -> base procedure;
5. applicable addons + quantities;
6. full-composition free dates/slots;
7. stale callback/state recovery;
8. fresh slot recheck before submit;
9. summary with fresh duration/price;
10. submit -> exactly one pending request;
11. pending does not reserve slot;
12. own request list/detail/cancel;
13. master approve -> confirmed booking visible to same client;
14. reject -> understandable recovery action;
15. no owner/client/master Telegram IDs or PII in callback;
16. callback <= 64 bytes;
17. no direct DB access/business logic in Telegram runtime;
18. client runtime can remain disabled until the complete flow and master-side request UX are accepted.

## 17. Implementation order after this spec

1. Master cabinet: incoming requests + explicit create/link + approve/reject.
2. Backend composition-aware public slots/request summary contract.
3. Server-side client booking draft / compact flow handles for addons and quantities.
4. Telegram UX refactor to this spec: home, price, service, addons, dates, slots, summary, request state.
5. Own requests/confirmed bookings view.
6. Only then enable a real client Telegram bot in a controlled acceptance environment and run full E2E.
