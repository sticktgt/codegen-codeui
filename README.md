# codeui

`codeui` — веб-интерфейс и FastAPI-фасад для управляемой работы с `codecollector`.

Приложение предназначено для рабочего сценария, в котором аналитик выбирает проект, подключает файл требований, создает запрос на изменение, выполняет анализ, выбирает место изменения, запускает обработку, просматривает результат и принимает решение о применении изменений к основному проекту.

`codeui` не реализует собственный pipeline изменения кода. Pipeline выполняется в `codecollector`; `codeui` управляет пользовательским workflow, хранит собственные запросы на изменение, вызывает `codecollector` через CLI и отображает компактные представления JSON-артефактов запусков.

## Основной порядок работы

1. Выбрать проект.
2. Подключить файл требований.
3. Выбрать требование.
4. Создать запрос на изменение.
5. Выполнить анализ запроса.
6. Посмотреть кандидатов места изменения.
7. Выбрать место изменения из списка или ввести его вручную.
8. Запустить обработку.
9. Посмотреть результат, шаги, проверки, diff, сгенерированный код и тест.
10. Применить результат к основному проекту отдельным решением пользователя.

## Текущий функционал

- Выбор проекта из списка проектов, зарегистрированных в `codecollector`.
- Регистрация нового проекта через `codecollector`.
- Сохранение выбранного проекта в UI-состоянии.
- Подключение JSON-файла требований.
- Отображение требований в иерархическом списке по `parent_id`.
- Просмотр выбранного требования.
- Создание запроса на изменение, связанного с одним или несколькими требованиями.
- Сохранение snapshot требований внутри запроса на изменение.
- Короткий код запроса вида `CR-000001` для удобного отображения в UI.
- Редактирование запроса до применения результата к основному проекту.
- Удаление запроса до применения результата к основному проекту.
- Выполнение анализа запроса.
- Выбор места изменения из кандидатов анализа.
- Ручной ввод места изменения.
- Запуск обработки через `codecollector`.
- Хранение связи запроса со связанными запусками.
- Просмотр запусков, связанных с выбранным запросом.
- Просмотр общего списка запусков.
- Ограничение общего списка запусков по умолчанию с возможностью загрузить весь список.
- Просмотр результата запуска: summary, шаги, проверки, diff, код, тест.
- Отображение ошибок проверок с кодом, сообщением, файлом, символом и раскрываемыми деталями.
- Применение последнего результата запроса к основному проекту.

## Статусы запроса

`applied` — финальный статус запроса. Он означает, что результат был применен к основному проекту.

Для запроса в статусе `applied` недоступны:

- редактирование;
- удаление;
- повторный анализ;
- повторный выбор места изменения;
- повторный запуск обработки;
- повторное применение результата.

Статус `ready_for_merge_review` не является финальным. В этом состоянии результат готов к ручной проверке, но запрос еще можно изменить и обработать заново.

## Структура проекта

```text
codeui/
  README.md
  pyproject.toml
  config.yaml
  data/
    requirements.json
    ui_state.json
    change_requests/
  codeui/
    main.py
    __main__.py
    config.py
    logger.py
    errors.py
    dependencies.py
    api/
    schemas/
    services/
    static/
```

## Конфигурация

Все настройки окружения и константы хранятся в `config.yaml`.

```yaml
app:
  name: "codeui"
  version: "0.2.7"

server:
  host: "127.0.0.1"
  port: 8088
  reload: false

codecollector:
  root_dir: "../codecollector"
  python: "python"
  module: "codecollector"
  command_timeout_sec: 900
  runs_dir: ".runs"
  state_dir: ".state"
  workspaces_dir: ".workspaces"

requirements:
  sources:
    - id: "demo"
      type: "json_file"
      path: "data/requirements.json"
      enabled: true

change_requests:
  storage_dir: "data/change_requests"

ui:
  poll_interval_ms: 1500
  show_raw_json: true
  show_debug_artifacts: true
  state_file: "data/ui_state.json"
```

`config.yaml` не хранит текущий выбор пользователя. Текущий проект, путь к файлу требований, выбранное требование и выбранный запрос сохраняются в `data/ui_state.json`.

## Формат требований

Поддерживается JSON-файл с массивом `requirements`:

```json
{
  "requirements": [
    {
      "id": "LLM-A-000011",
      "type": "BR",
      "status": "новое",
      "description": "...",
      "parent_id": null,
      "verification_status": "верифицировано"
    }
  ]
}
```

Также допускается список требований на верхнем уровне.

Для отображения используются поля:

- `id`;
- `type`;
- `description`;
- `status`;
- `priority`;
- `parent_id`;
- `verification_status`;
- `note`;
- `created_at`;
- `project_id`.

Если поле `title` отсутствует, заголовок строится из начала `description`.

## Запросы на изменение

Запросы на изменение хранятся в `data/change_requests` как отдельные JSON-файлы.

Пример структуры:

```json
{
  "cr_id": "cr-20260428T112246024228Z-4dd977",
  "code": "CR-000001",
  "project_id": "proj-...",
  "requirement_id": "LLM-A-000011",
  "requirement_ids": ["LLM-A-000011"],
  "requirements_snapshot": [
    {
      "id": "LLM-A-000011",
      "description": "...",
      "type": "BR",
      "verification_status": "верифицировано",
      "missing": false
    }
  ],
  "title": "...",
  "description": "...",
  "constraints": [],
  "notes": [],
  "requested_operation": "replace_symbol",
  "status": "draft",
  "session_id": null,
  "recommended_target": null,
  "selected_target": null,
  "run_ids": [],
  "last_run_id": null,
  "last_workspace_id": null,
  "applied_at": null,
  "applied_run_id": null
}
```

`requirements_snapshot` нужен для устойчивости: если файл требований недоступен или требование исчезло, уже созданный запрос все равно можно открыть и просмотреть.

Поле `code` используется для компактного отображения запроса в UI. В `codecollector` оно не передается.

## API

Основные endpoint-ы:

```text
GET  /api/settings
GET  /api/ui-state
PUT  /api/ui-state
POST /api/ui-state/select-project
POST /api/ui-state/requirements-file

GET  /api/projects
POST /api/projects/register

GET  /api/requirements
GET  /api/requirements/tree
GET  /api/requirements/{requirement_id}

GET    /api/change-requests
GET    /api/change-requests?requirement_id=...
POST   /api/change-requests
GET    /api/change-requests/{cr_id}
PUT    /api/change-requests/{cr_id}
DELETE /api/change-requests/{cr_id}
GET    /api/change-requests/{cr_id}/runs
POST   /api/change-requests/{cr_id}/analyze
POST   /api/change-requests/{cr_id}/select-target
POST   /api/change-requests/{cr_id}/run
POST   /api/change-requests/{cr_id}/apply-last-run

GET  /api/runs
GET  /api/runs?limit=50
GET  /api/runs?all=true
GET  /api/runs/{run_id}/summary
GET  /api/runs/{run_id}/steps
GET  /api/runs/{run_id}/checks
GET  /api/runs/{run_id}/diff
GET  /api/runs/{run_id}/code
GET  /api/runs/{run_id}/test
GET  /api/runs/{run_id}/raw
```

## Запуск

```bash
cd /home/stickt/llm/codeui
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m codeui
```

По умолчанию приложение доступно по адресу:

```text
http://127.0.0.1:8088/
```

## Логирование и ошибки

`codeui` логирует:

- вызовы CLI `codecollector`;
- рабочую директорию и команду;
- код возврата;
- длительность;
- размер stdout/stderr;
- ошибки чтения JSON;
- изменения UI-состояния;
- создание и изменение запросов на изменение;
- применение результата к основному проекту.

Ошибки API возвращаются в едином формате:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}
```

## Текущие ограничения

- Аутентификация и авторизация не реализованы.
- Проекты не хранятся в `codeui`; список читается из `codecollector`.
- Требования подключаются как JSON-файл и не редактируются в UI.
- Pipeline выполняется в `codecollector`.
- Связь между запросом и запусками хранится в JSON-файле запроса.
- Общее хранилище состояния — файловое, без отдельной базы данных.
- Применение результата выполняется только после отдельного решения пользователя.
