# Nails — shutdown/restart Telegram notification disabled

Дата production-приёмки: **17 июля 2026 года**.

Связанные GitHub-объекты:

- issue #101 — закрыт как выполненный;
- PR #102 — закрыт без merge, потому что production-настройка была выполнена отдельно.

## Цель

Для Hermes-профиля `nails` полностью отключить Telegram-сообщение:

```text
Gateway shutting down — Your current task will be interrupted
```

при плановой остановке или перезапуске `hermes-gateway-nails.service`.

## Подтверждённый результат

VPS-агент вернул итоговую production-проверку:

```text
profile=nails
telegram_gateway_restart_notification=false
gateway_active=true
api_health=true
api_readiness=true
SHUTDOWN_NOTIFICATION_DISABLED=true
```

До изменения read-only preflight подтвердил:

```text
hostname=de.funti.cc
checkout_sha=bfcdc0fb9f1ef28b211b450bfc4f59995bb4728e
working_tree_clean=true
hermes_version=0.18.2
gateway_package=/usr/local/lib/hermes-agent/gateway/__init__.py
matching_module=/usr/local/lib/hermes-agent/gateway/run.py
runner_class=GatewayRunner
shutdown_method_source=/usr/local/lib/hermes-agent/gateway/run.py
gateway_active=true
api_health=true
api_readiness=true
SHUTDOWN_NOTIFICATION_PREFLIGHT_OK=true
```

## Граница действия

- уведомления отключены только для профиля `nails`;
- оба мастера не получают shutdown/restart сообщение;
- другие Hermes-профили не затронуты;
- gateway после перезапуска активен;
- backend API health/readiness успешны.

## Операционное правило

После обновления Hermes, изменения profile runtime или unit-файла необходимо повторно проверить:

```text
telegram_gateway_restart_notification=false
```

и выполнить реальный контролируемый restart с подтверждением, что ни одному мастеру не пришло shutdown/restart сообщение. Не считать отсутствие сообщения гарантированным только по успешному `systemctl restart`.

Секреты, Telegram identifiers и содержимое environment-файлов в отчёт не включаются.
