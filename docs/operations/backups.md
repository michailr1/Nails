# Nails production backups

Этот документ — source of truth для постоянного механизма NAILS-002F. Он читается вместе с `production-infrastructure.md`, `engineering-principles.md` и ADR-003.

## Runtime

```text
backup runtime: /opt/nails/backup
backup root: /opt/nails/backups
service: nails-backup.service
system timer: nails-backup.timer
schedule: daily 03:30 UTC, Persistent=true, randomized delay up to 15 minutes
profile env: /root/.hermes/profiles/nails/.env
```

Установка и обновление выполняются только постоянным `ops/deploy/deploy.sh`. Candidate устанавливает тот же runtime и timer, которые останутся после fast-forward merge. Одноразовые install-скрипты запрещены.

## Успешный запуск

Backup считается успешным только если последовательно выполнено всё:

1. создан непустой `/opt/nails/backups/daily/nails-<UTC>.sql.gz`;
2. пройден `gzip -t`;
3. сняты Alembic revision и row counts всех таблиц схемы `public` production DB;
4. создана отдельная временная DB;
5. dump восстановлен с `ON_ERROR_STOP=1`;
6. Alembic revision и row counts восстановленной DB совпали с source;
7. временная DB удалена;
8. применена retention policy;
9. archive отправлен администратору через Telegram, если размер не превышает 15 MiB;
10. записан `/opt/nails/backups/status/last-success` и удалён `last-failure`.

Любая ошибка делает systemd service failed и создаёт `status/last-failure`. Telegram failure не удаляет уже проверенную локальную копию, но весь запуск считается failed.

## Telegram secrets

В profile `.env` должны существовать:

```text
TELEGRAM_BOT_TOKEN или TELEGRAM_TOKEN
NAILS_BACKUP_TELEGRAM_CHAT_ID
```

Значения не печатаются, не коммитятся и не включаются в отчёты. Архив отправляется без дополнительного шифрования согласно принятой политике issue #91.

## Retention

- daily: последняя копия каждого из последних 5 UTC-дней;
- weekly: последние 3 ISO-недели;
- monthly: последние 12 месяцев;
- pre-deploy DB: все за последние 24 часа, затем максимум одна в день до общего возраста 5 дней;
- successful runtime deploy backups: последние 2;
- failed runtime deploy backups: 3 дня;
- backup logs: 14 дней;
- `hermes-local-patches`: никогда не удаляется retention-механизмом.

`retention.py` без `--apply` работает как dry-run и только печатает точные пути `REMOVE`.

## Disk thresholds

- 80%: `DISK_WARNING`, backup остаётся успешным;
- 90%: `DISK_CRITICAL`, локальная проверенная копия сохраняется, но запуск считается failed.

## Проверки production

```bash
systemctl is-enabled nails-backup.timer
systemctl is-active nails-backup.timer
systemctl list-timers nails-backup.timer --no-pager
systemctl start nails-backup.service
systemctl status nails-backup.service --no-pager
journalctl -u nails-backup.service --since today --no-pager
cat /opt/nails/backups/status/last-success
```

Не выводить profile `.env`, Telegram token/chat ID, содержимое dump или полные environment-переменные.

## Restore incident

Автоматический restore-test не заменяет процедуру восстановления production. При инциденте нельзя восстанавливать поверх рабочей DB ad-hoc командами. Сначала выбрать проверенный dump, развернуть отдельную DB, подтвердить Alembic/counts и только затем подготовить отдельный reviewable recovery runbook основным агентом.
