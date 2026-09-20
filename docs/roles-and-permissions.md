# Роли и полномочия

Дата актуализации: **20 сентября 2026 года**.

## 1. Уровни identity

В Nails разделены:

1. Telegram allowlist/Hermes identity доверенного мастера;
2. business role `master/admin`;
3. web session/effective owner;
4. client transport identity отдельного Telegram-бота;
5. PostgreSQL application/admin roles.

Ни один уровень не должен подменять другой.

## 2. `master`

Мастер работает только со своими owner-scoped данными.

Разрешено:

- onboarding и настройки;
- расписание/исключения;
- прайс;
- клиентские карточки и private notes;
- bookings;
- заявки клиенток;
- linking/resolve identity;
- approve/reject;
- public profile;
- general/personal invite links;
- статистика и выгрузки.

Запрещено:

- читать данные другого owner;
- менять системные роли/secrets;
- direct SQL/shell через продуктовый интерфейс;
- обходить обязательные подтверждения;
- публиковать private client fields.

## 3. `admin`

Admin имеет master business access в разрешённых границах плюс контролируемые administrative lifecycle/diagnostic операции.

Admin не получает unrestricted shell/SQL через Telegram-модель и не может обычной командой отключить owner checks/audit.

## 4. Client transport identity

Client — не operator `users.role` и не Hermes profile.

Доверенными источниками являются:

- отдельный `CLIENT_INTERNAL_API_KEY`;
- Telegram user ID из проверенного Update;
- server-side binding/context;
- server-side start-token resolution.

**Owner больше не задаётся конфигурацией одного мастера.** Модель ADR-009:

```text
start_token -> owner_user_id   (server-side only)
telegram_user_id + owner_user_id -> owner-scoped binding
```

Клиент не может передать произвольные `owner_user_id`, `client_id`, role или чужой Telegram ID через body/query.

## 5. Что client может

- открыть ссылку конкретного мастера;
- видеть public master profile;
- видеть public price;
- получать free slots;
- создавать/изменять собственный server-side draft;
- отправлять собственную BookingRequest;
- видеть собственные актуальные заявки/подтверждённые записи;
- отменять разрешённые собственные pending-действия;
- передавать contact через Telegram ownership flow;
- отправить короткое пояснение мастеру как информацию;
- переключаться только между мастерами, с которыми уже есть binding.

## 6. Что client не может

- подтверждать Booking;
- резервировать slot pending-заявкой;
- auto-link карточку по имени/телефону;
- видеть чужие requests/bookings;
- видеть internal alias/notes;
- выбирать owner из глобального списка;
- видеть numeric Telegram ID мастера;
- получать personal Telegram username мастера без explicit `public_contact`.

## 7. Public profile мастера

Client-facing identity строится из `master_public_profile`:

- `display_name` — обязательный gate invite link;
- `public_contact` — nullable, opt-in.

Telegram account fields мастера не являются автоматическим public profile.

## 8. Multi-binding

Одна Telegram-клиентка может иметь несколько независимых binding'ов к разным owners.

«Ваши мастера» содержит только эти binding'и. Публичного directory/discovery нет.

## 9. Runtime boundaries

Master Hermes key и client internal key различаются. Master/client Telegram tokens также должны различаться.

Client runtime не получает direct DB access. Его полномочия ограничены client API + notification claim/ack transport.

## 10. Production roles

Release/deploy роли:

- основной ChatGPT — repo/code/tests/docs/PR/CI;
- VPS-agent — candidate/deploy/runtime acceptance/rollback;
- пользователь не обязан выдавать пошаговые технические инструкции.
