# Развёртывание Nails на VPS

Production-контур размещается только в отдельном каталоге `/opt/nails/` и не использует секреты других проектов.

## Файлы окружения

1. Скопировать `.env.example` в `/opt/nails/.env`.
2. Задать отдельную bootstrap-пару `POSTGRES_ADMIN_USER` и `POSTGRES_ADMIN_PASSWORD`.
3. Задать отдельную прикладную пару `APP_DB_USER` и `APP_DB_PASSWORD`, затем собрать `DATABASE_URL` с прикладным пользователем.
4. Обязательно указать `APP_TIMEZONE` в формате IANA.
5. Установить права `chmod 600 /opt/nails/.env`.

Bootstrap-пользователь нужен только при первом создании PostgreSQL volume. API подключается через ограниченного `APP_DB_USER` без прав `SUPERUSER`, `CREATEDB`, `CREATEROLE` и `REPLICATION`.

Ни `.env`, ни резервные копии базы не добавляются в GitHub.

## Сети

- `nails-db` подключён только к изолированной сети `nails-internal` и не публикует порт на VPS;
- `nails-api` подключён к `nails-internal` для доступа к базе и к отдельной `nails-edge` для локального HTTP-порта;
- API по умолчанию публикуется только на `127.0.0.1:8210` и не доступен напрямую из внешней сети.

## Запуск

```bash
cd /opt/nails/repo
docker compose --env-file /opt/nails/.env up -d --build
```

## Проверка

```bash
curl -fsS http://127.0.0.1:8210/health
curl -fsS http://127.0.0.1:8210/ready
docker compose ps
```

Перед пилотом отдельно настраиваются автоматические внешние резервные копии и проверка восстановления в рамках NAILS-002F.
