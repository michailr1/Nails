# Nails Telegram — отображение tool-вызовов

## Цель

В Telegram мастер не должен видеть техническую строку Hermes вида:

```text
⚙️ nails_onboarding... (×2)
```

Вместо неё onboarding skill перед группой последовательных вызовов показывает обычное сообщение:

```text
Думаю… (nails_onboarding)
```

## Runtime configuration

В profile-local `config.yaml` профиля `nails` должна быть установлена конфигурация:

```yaml
display:
  platforms:
    telegram:
      tool_progress: off
      interim_assistant_messages: true
```

`tool_progress: off` скрывает стандартный технический breadcrumb Hermes.

`interim_assistant_messages: true` позволяет доставить отдельное короткое сообщение skill перед вызовом restricted tool.

Настройка применяется только к профилю `nails`. Нельзя менять глобальную конфигурацию Hermes или настройки других профилей.

## Диалоговый контракт

- Перед одной группой последовательных вызовов показывается одна строка `Думаю… (nails_onboarding)`.
- Счётчик вызовов, аргументы и технические идентификаторы не показываются.
- После завершения tool-вызовов бот продолжает обычный человеческий диалог.
- При отсутствии tool-вызова строка `Думаю…` не отправляется.
