# Concise VPS reporting contract

Status: **mandatory for new Nails deployment and diagnostic prompts**.

Полный вывод команд остаётся на production-сервере в root-only логе по пути, который печатает runbook/скрипт. В чат возвращается только компактная сводка в каноническом формате ниже. При необходимости основной агент запрашивает конкретный небольшой фрагмент лога.

## Канонический формат: успех

```text
RESULT=success
runbook=<id или deploy.sh>
head=<sha-before> -> <sha-after>
backups=db:ok,runtime:ok
checks=api:ok,gateway:ok,plugins:ok,isolation:ok
mutations=schema:false,data:false,config:false
rollback=not-required
details_log=<путь к полному логу на сервере>
```

## Канонический формат: ошибка

```text
RESULT=failed
runbook=<id или deploy.sh>
phase=<этап>
failed_check=<конкретная проверка или команда>
error=<одна безопасная строка ошибки>
head_current=<sha>
backups=db:ok,runtime:ok
rollback=performed|not-required|failed
rollback_result=api:ok,gateway:active,head:<sha>
details_log=<путь к полному логу на сервере>
```

Маркер неудавшегося rollback никогда не сокращается и не опускается. При ошибке сборки или падении сервиса допускается приложить до 60 релевантных строк лога, если сам runbook их печатает.

## Что не возвращается в чат

- статистика файлов `git merge`/`git diff`;
- слои Docker build и вывод установки пакетов;
- повторяющиеся успешные проверки;
- полные журналы сервисов;
- любые секреты и персональные данные.

## Шаблон для промптов основного агента

```text
Верни отчёт строго в каноническом формате RESULT=… из docs/operations/vps-reporting.md.
Полный вывод сохрани в root-only лог и укажи details_log. Не вставляй git stat,
Docker build layers, pip output или полный journal. При ошибке rollback-блок обязателен.
```

Правило сокращает рост контекста чата без потери аудируемости: полные логи остаются на сервере.
