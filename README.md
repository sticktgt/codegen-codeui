# codeui

`codeui` — web-интерфейс и FastAPI-фасад для управляемой работы с запросами на изменение кода через `codecollector`.

Приложение предназначено для рабочего сценария, в котором пользователь выбирает проект, подключает файл требований, создает запрос на изменение, выполняет анализ, выбирает место изменения, запускает обработку, просматривает результат и принимает решение о применении изменений к основному проекту.

`codeui` не реализует собственный pipeline изменения кода. Он управляет пользовательским workflow, хранит запросы на изменение, вызывает `codecollector` через CLI и отображает компактные представления JSON-артефактов запусков.

## Основной сценарий работы

1. Пользователь выбирает проект из списка проектов, зарегистрированных в `codecollector`, или регистрирует новый проект.
2. Пользователь подключает JSON-файл требований.
3. Пользователь выбирает требование в иерархическом списке.
4. Пользователь создает запрос на изменение, связанный с выбранным требованием.
5. Пользователь выполняет анализ запроса.
6. Приложение показывает качество запроса, рекомендованную операцию, рекомендацию места изменения и кандидатов.
7. Пользователь выбирает место изменения из кандидатов или вводит qualname вручную.
8. Пользователь запускает обработку.
9. Приложение показывает результат запуска: summary, шаги, проверки, статистику, план применения, diff, сгенерированный код и тест.
10. Пользователь принимает отдельное решение о применении последнего результата к основному проекту.

## Текущий функционал

`codeui` поддерживает:

- выбор активного проекта из проектов `codecollector`;
- регистрацию нового проекта через `codecollector`;
- сохранение текущего UI-состояния в JSON-файле;
- подключение JSON-файла требований;
- отображение требований деревом по `parent_id`;
- просмотр карточки выбранного требования;
- создание запроса на изменение, связанного с одним или несколькими требованиями;
- сохранение snapshot требований внутри запроса;
- короткий пользовательский код запроса вида `CR-000001`;
- редактирование запроса до финального применения результата;
- удаление запроса до финального применения результата;
- анализ запроса без обязательного ручного выбора операции;
- отображение качества запроса и недостающей информации;
- отображение рекомендованной операции с источником, уверенностью и причиной;
- отображение рекомендации места изменения или anchor для вставки;
- отображение LLM-rerank кандидатов;
- ручной выбор места изменения из кандидатов;
- ручной ввод qualname места изменения;
- блокировку обработки для недостаточно конкретного запроса;
- запуск обработки через `codecollector`;
- хранение связи запроса с запусками;
- просмотр запусков, связанных с выбранным запросом;
- просмотр общего списка запусков;
- ограничение общего списка запусков по умолчанию;
- открытие конкретного запуска напрямую из карточки запроса;
- отображение результата запуска в компактном виде;
- отображение ошибок проверок с кодом, сообщением, файлом, символом и деталями;
- применение последнего результата запроса к основному проекту.

## Структура проекта

```text
codeui/
  README.md
  AGENTS.md
  pyproject.toml
  config.yaml
  data/
    requirements.json
    ui_state.json
    change_requests/
  codeui/
    __init__.py
    __main__.py
    main.py
    config.py
    dependencies.py
    errors.py
    logger.py
    api/
    schemas/
    services/
    static/
```

### Основные файлы верхнего уровня

| Файл или каталог | Назначение |
|---|---|
| `README.md` | Описание текущего состояния проекта, запуска, структуры, API и ограничений. |
| `AGENTS.md` | Контекст для агента, который дорабатывает проект. |
| `pyproject.toml` | Метаданные Python-проекта и зависимости. |
| `config.yaml` | Основная конфигурация приложения. |
| `data/requirements.json` | Дефолтный файл требований для локального запуска. |
| `data/ui_state.json` | Текущее состояние UI: выбранный проект, файл требований, выбранное требование и выбранный запрос. |
| `data/change_requests/` | JSON-файлы запросов на изменение. |

### Backend

| Файл или каталог | Назначение |
|---|---|
| `codeui/main.py` | Создание FastAPI-приложения, подключение роутеров и static UI. |
| `codeui/__main__.py` | Точка запуска `python -m codeui`. |
| `codeui/config.py` | Загрузка и нормализация `config.yaml`. |
| `codeui/dependencies.py` | Создание сервисов и зависимостей FastAPI. |
| `codeui/errors.py` | Единый формат API-ошибок и исключения приложения. |
| `codeui/logger.py` | Настройка логирования. |
| `codeui/api/` | FastAPI-роутеры. |
| `codeui/schemas/` | Pydantic-схемы входных и выходных данных. |
| `codeui/services/command_runner.py` | Выполнение внешних CLI-команд с логированием. |
| `codeui/services/codecollector_client.py` | CLI-клиент для вызова `codecollector`. |
| `codeui/services/change_request_service.py` | Создание, изменение, удаление CR и управление их lifecycle. |
| `codeui/services/requirements_service.py` | Чтение требований из JSON и построение дерева. |
| `codeui/services/run_artifact_service.py` | Поиск и чтение артефактов запусков из `.runs`. |
| `codeui/services/run_view_service.py` | Построение компактных view-models для результатов запуска. |
| `codeui/services/ui_state_service.py` | Чтение и запись состояния UI. |
| `codeui/services/json_io.py` | Безопасное чтение и запись JSON-файлов. |

### Frontend

| Файл | Назначение |
|---|---|
| `codeui/static/index.html` | Основная HTML-страница приложения. |
| `codeui/static/styles.css` | Компактная desktop/form-like визуальная схема. |
| `codeui/static/app.js` | Клиентская логика UI, вызовы API и отрисовка экранов. |

## Конфигурация

Основной файл конфигурации — `config.yaml`.

```yaml
app:
  name: "codeui"
  version: "0.2.13"

server:
  host: "127.0.0.1"
  port: 8088
  reload: false

logging:
  level: "INFO"

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
  default_runs_limit: 50
```

`config.yaml` хранит настройки окружения, пути и режимы работы приложения. Текущий выбор пользователя в нем не хранится.

Текущее пользовательское состояние хранится в `data/ui_state.json`:

```json
{
  "selected_project_id": "proj-...",
  "requirements_file_path": "data/requirements.json",
  "selected_requirement_ids": ["REQ-..."],
  "selected_change_request_id": "cr-..."
}
```

## Требования

Требования подключаются как JSON-файл. Поддерживается объект с массивом `requirements`:

```json
{
  "requirements": [
    {
      "id": "LLM-A-000011",
      "type": "BR",
      "status": "новое",
      "priority": "medium",
      "description": "Система должна ...",
      "parent_id": null,
      "verification_status": "верифицировано",
      "note": "...",
      "created_at": "2026-04-01T12:00:00Z"
    }
  ]
}
```

Также допускается список требований на верхнем уровне:

```json
[
  {
    "id": "LLM-A-000011",
    "type": "BR",
    "description": "..."
  }
]
```

Требования в `codeui` доступны только для чтения. Приложение не редактирует файл требований.

Для отображения используются поля:

- `id`;
- `title`, если есть;
- `description`;
- `type`;
- `status`;
- `priority`;
- `parent_id`;
- `verification_status`;
- `note`;
- `created_at`;
- `project_id`.

Иерархия строится по `parent_id`. Если `title` отсутствует, заголовок строится из начала `description`.

## Запрос на изменение

Запрос на изменение, или CR, — сущность `codeui`. CR связывает выбранный проект, требования, описание изменения, сессию анализа, выбранное место изменения и запуски обработки.

CR хранится отдельным JSON-файлом в `data/change_requests/`.

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
  "title": "Изменить текст уведомления",
  "description": "Сделать уведомление на русском языке.",
  "constraints": ["Не менять внешний контракт API"],
  "notes": [],
  "requested_operation": null,
  "status": "draft",
  "session_id": null,
  "recommended_target": null,
  "selected_target": null,
  "run_ids": [],
  "last_run_id": null,
  "last_workspace_id": null,
  "applied_at": null,
  "applied_run_id": null,
  "raw": {}
}
```

`code` — короткий пользовательский идентификатор, например `CR-000001`. `cr_id` — технический идентификатор.

`requirements_snapshot` нужен для устойчивого отображения CR, если исходный файл требований недоступен или требование больше не найдено.

`requested_operation` — операция, выбранная пользователем вручную. Если значение `null`, анализ вызывается без операции, а `codecollector` пытается определить ее автоматически.

Результат последнего анализа сохраняется в `raw.last_analyze_result`. Из него UI берет качество запроса, рекомендованную операцию, источник операции, рекомендацию места изменения, кандидатов, предупреждения и статистику анализа.

## Статусы запроса

| Статус | Значение |
|---|---|
| `draft` | Запрос создан, анализ еще не выполнен или исходные поля были изменены. |
| `analyzed` | Анализ выполнен, запрос можно продолжать обрабатывать. |
| `needs_user_decision` | Требуется действие пользователя: выбрать место изменения, уточнить операцию или изменить запрос. |
| `analysis_insufficient` | Запрос недостаточно конкретный, обработка заблокирована до редактирования и повторного анализа. |
| `target_selected` | Место изменения выбрано. |
| `running` | Выполняется действие или обработка. |
| `ready_for_merge_review` | Результат готов к ручной оценке и применению. |
| `verification_failed` | Проверки не пройдены. |
| `generated_test_verification_failed` | Основной код прошел проверки, но возникла проблема со сгенерированным тестом. |
| `failed` | Ошибка выполнения действия. |
| `applied` | Результат применен к основному проекту. |

Финальный статус — только `applied`. Для CR в статусе `applied` недоступны редактирование, удаление, повторный анализ, повторный выбор места изменения, повторный запуск обработки и повторное применение результата.

`ready_for_merge_review` не является финальным статусом. В этом состоянии CR можно изменить и обработать заново.

## Анализ запроса

Анализ запускается командой `codecollector sessions analyze`. Если пользователь не выбрал операцию вручную, `codeui` вызывает анализ без `--operation`. Если операция выбрана вручную, она передается явно.

Анализ может вернуть качество запроса:

| Значение | Поведение UI |
|---|---|
| `processable` | Запрос достаточно конкретный, workflow можно продолжать. |
| `uncertain` | Запрос частично неясный, можно продолжать с предупреждением и ручной проверкой. |
| `insufficient` | Запрос слишком общий, обработку нужно блокировать. |

Если `request_quality.status = insufficient`, UI показывает причину и `missing_information`, не разрешает выбор места изменения как обход и не запускает обработку. Пользователь должен изменить название, описание или ограничения CR и выполнить анализ заново.

Анализ также возвращает сведения об операции:

| Поле | Значение |
|---|---|
| `requested_operation` | Итоговая операция, с которой работал analyze. |
| `operation_source` | Источник определения операции. |
| `operation_confidence` | Уверенность определения операции. |
| `operation_reason` | Объяснение выбора операции. |

Возможные `operation_source`:

| Значение | Значение для UI |
|---|---|
| `user` | Операцию явно выбрал пользователь. |
| `llm_search_plan` | Операция определена LLM на этапе плана поиска. |
| `llm_rerank` | Операция уточнена LLM после просмотра кандидатов. |
| `fallback` | Операция не определена надежно, использовано техническое значение по умолчанию. |

Если `operation_source = fallback`, операция не считается надежно выбранной. Перед выбором места изменения и запуском обработки пользователь должен выбрать операцию вручную.

Рекомендация места изменения находится в `target_recommendation`:

| Поле | Назначение |
|---|---|
| `recommended_target` | Рекомендованный qualname. |
| `target_role` | Роль выбранного места: `target`, `anchor` или `unknown`. |
| `target_confidence` | Уверенность выбора. |
| `target_reason` | Объяснение рекомендации. |
| `manual_review_required` | Признак необходимости ручной проверки. |
| `warnings` | Предупреждения анализа. |
| `ranked_candidates` | Результат LLM-rerank кандидатов. |
| `post_processing` | Дополнительная информация о корректировке anchor, если она применялась. |

Для `insert_after_symbol` роль `anchor` означает, что выбранный symbol является местом, после которого будет вставлен новый код.

## Кандидаты места изменения

Кандидаты отображаются после анализа. Для каждого кандидата используются поля:

- `qualname`;
- `name`;
- `kind`;
- `file_path`;
- `score`;
- `confidence`;
- `relevance_category`;
- `reasons`;
- `docstring`;
- `knowledge_title`;
- `requirements`;
- `ranked_by_llm`;
- `llm_recommended`;
- `llm_rank`;
- `llm_reason`.

Если `llm_recommended = true`, кандидат является основной рекомендацией LLM. Если `ranked_by_llm = false`, кандидат найден поиском, но не участвовал в финальном LLM-rerank.

Выбор места изменения выполняется через `sessions select-target`. При выборе передается qualname и операция. Операция должна быть заполнена надежным значением: выбранным пользователем или принятым из результата анализа.

## Запуски и результаты обработки

Запуски физически хранятся в `.runs` проекта `codecollector`. `codeui` не копирует тяжелые артефакты в свое хранилище.

Типовая структура run-директории:

```text
codecollector/.runs/pipeline-.../
  pipeline_run_*.json
  generation_request.json
  generation_result.json
  generation_test_request.json
  generation_test_result.json
  repair_request.json
  repair_result.json
  codegenerator_stderr.txt
  codegenerator_test_stderr.txt
```

CR хранит связь с запусками через поля `run_ids` и `last_run_id`. Экран CR показывает только связанные с ним запуски. Экран `Запуски` показывает последние N запусков и может открыть конкретный запуск напрямую.

Результат запуска отображается компактно:

- общий результат;
- основная проблема, если запуск завершился ошибкой;
- план применения;
- список шагов с таймингами и usage;
- проверки;
- diff;
- сгенерированный код;
- сгенерированный тест;
- статистика ресурсов.

Raw JSON используется как дополнительная возможность просмотра, а не как основной экран.

## Применение результата

Применение результата выполняется отдельным действием пользователя. Применять можно только последний запуск выбранного CR.

После успешного применения:

- CR получает статус `applied`;
- сохраняются `applied_at` и `applied_run_id`;
- дальнейшее редактирование, удаление, анализ, запуск обработки и повторное применение блокируются.

## API

Все endpoint-ы используют префикс `/api`.

Ошибки возвращаются в едином формате:

```json
{
  "error": {
    "code": "RUN_NOT_FOUND",
    "message": "Run not found: pipeline-...",
    "details": {}
  }
}
```

### Health и настройки

#### `GET /api/health`

Проверяет доступность приложения.

Пример ответа:

```json
{
  "status": "ok",
  "app": "codeui"
}
```

#### `GET /api/settings`

Возвращает основные настройки приложения без изменения состояния.

Пример:

```bash
curl http://127.0.0.1:8088/api/settings
```

Пример ответа:

```json
{
  "app_name": "codeui",
  "app_version": "0.2.13",
  "codecollector_root": "/home/stickt/llm/codecollector",
  "runs_root": "/home/stickt/llm/codecollector/.runs",
  "workspaces_root": "/home/stickt/llm/codecollector/.workspaces",
  "change_requests_root": "/home/stickt/llm/codeui/data/change_requests",
  "ui": {
    "poll_interval_ms": 1500,
    "show_raw_json": true,
    "show_debug_artifacts": true
  }
}
```

### UI-состояние

#### `GET /api/ui-state`

Возвращает текущий выбранный проект, файл требований, выбранные требования и выбранный CR.

```bash
curl http://127.0.0.1:8088/api/ui-state
```

#### `PUT /api/ui-state`

Обновляет UI-состояние.

```bash
curl -X PUT http://127.0.0.1:8088/api/ui-state \
  -H 'Content-Type: application/json' \
  -d '{
    "selected_project_id": "proj-20260401T124114819654Z-107054",
    "requirements_file_path": "data/requirements.json",
    "selected_requirement_ids": ["LLM-A-000011"],
    "selected_change_request_id": "cr-..."
  }'
```

#### `POST /api/ui-state/select-project`

Сохраняет выбранный проект.

```bash
curl -X POST http://127.0.0.1:8088/api/ui-state/select-project \
  -H 'Content-Type: application/json' \
  -d '{"project_id":"proj-20260401T124114819654Z-107054"}'
```

#### `POST /api/ui-state/requirements-file`

Сохраняет путь к файлу требований.

```bash
curl -X POST http://127.0.0.1:8088/api/ui-state/requirements-file \
  -H 'Content-Type: application/json' \
  -d '{"path":"/home/stickt/llm/codeui/data/requirements.json"}'
```

### Проекты

#### `GET /api/projects`

Возвращает проекты, зарегистрированные в `codecollector`.

```bash
curl http://127.0.0.1:8088/api/projects
```

Пример ответа:

```json
{
  "items": [
    {
      "project_id": "proj-20260401T124114819654Z-107054",
      "project_name": "sample_python_app",
      "project_root": "/home/stickt/llm/codecollector/demo_projects/sample_python_app",
      "languages": ["python"],
      "status": "ready"
    }
  ],
  "count": 1
}
```

#### `POST /api/projects/register`

Регистрирует новый проект через `codecollector`.

```bash
curl -X POST http://127.0.0.1:8088/api/projects/register \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name": "my_app",
    "project_root": "/home/stickt/projects/my_app",
    "languages": ["python"]
  }'
```

### Требования

#### `GET /api/requirements`

Возвращает плоский список требований из выбранного JSON-файла.

```bash
curl http://127.0.0.1:8088/api/requirements
```

#### `GET /api/requirements/tree`

Возвращает дерево требований, построенное по `parent_id`.

```bash
curl http://127.0.0.1:8088/api/requirements/tree
```

#### `GET /api/requirements/{requirement_id}`

Возвращает одно требование.

```bash
curl http://127.0.0.1:8088/api/requirements/LLM-A-000011
```

### Запросы на изменение

#### `GET /api/change-requests`

Возвращает список CR. Можно фильтровать по требованию.

```bash
curl http://127.0.0.1:8088/api/change-requests
curl 'http://127.0.0.1:8088/api/change-requests?requirement_id=LLM-A-000011'
```

#### `POST /api/change-requests`

Создает CR.

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "proj-20260401T124114819654Z-107054",
    "requirement_ids": ["LLM-A-000011"],
    "code": "CR-000001",
    "title": "Изменить текст уведомления",
    "description": "Сделать уведомление на русском языке.",
    "constraints": ["Не менять внешний контракт API"],
    "requested_operation": null
  }'
```

#### `GET /api/change-requests/{cr_id}`

Возвращает CR.

```bash
curl http://127.0.0.1:8088/api/change-requests/cr-...
```

#### `PUT /api/change-requests/{cr_id}`

Обновляет CR. Если меняются исходные поля запроса, результаты анализа и последний run сбрасываются как устаревшие.

```bash
curl -X PUT http://127.0.0.1:8088/api/change-requests/cr-... \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Новое название",
    "description": "Новое описание",
    "constraints": ["Новое ограничение"],
    "requested_operation": "replace_symbol"
  }'
```

#### `DELETE /api/change-requests/{cr_id}`

Удаляет CR, если он не находится в статусе `applied`.

```bash
curl -X DELETE http://127.0.0.1:8088/api/change-requests/cr-...
```

#### `GET /api/change-requests/{cr_id}/runs`

Возвращает запуски, связанные с CR.

```bash
curl http://127.0.0.1:8088/api/change-requests/cr-.../runs
```

#### `POST /api/change-requests/{cr_id}/analyze`

Запускает анализ CR. Если `requested_operation = null`, операция не передается в `codecollector`, и analyze определяет ее автоматически.

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../analyze
```

Пример фрагмента ответа:

```json
{
  "session_id": "sess-...",
  "requested_operation": "replace_symbol",
  "operation_source": "llm_search_plan",
  "operation_confidence": 0.6,
  "request_quality": {
    "status": "processable",
    "reason": "...",
    "missing_information": []
  },
  "target_recommendation": {
    "recommended_target": "support_app.services.notification_service.build_assignment_message",
    "target_role": "target",
    "target_confidence": 0.95,
    "manual_review_required": false
  },
  "result_summary": {
    "status": "analyzed",
    "request_quality_status": "processable"
  }
}
```

#### `POST /api/change-requests/{cr_id}/select-target`

Фиксирует выбранное место изменения. Операция передается вместе с qualname.

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../select-target \
  -H 'Content-Type: application/json' \
  -d '{
    "selected_qualname": "support_app.services.notification_service.build_assignment_message",
    "operation": "replace_symbol"
  }'
```

#### `POST /api/change-requests/{cr_id}/run`

Запускает обработку CR. Обработка блокируется, если запрос недостаточно конкретный, операция не выбрана или место изменения не выбрано.

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../run
```

Если `codecollector` вернул бизнес-блокировку генерации, ответ не считается runtime-ошибкой. UI должен показать причину и рекомендуемое действие.

#### `POST /api/change-requests/{cr_id}/apply-last-run`

Применяет последний результат CR к основному проекту.

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../apply-last-run
```

### Сессии

#### `GET /api/sessions`

Возвращает список сессий `codecollector`, если соответствующий CLI-доступ доступен.

```bash
curl http://127.0.0.1:8088/api/sessions
```

#### `GET /api/sessions/{session_id}`

Возвращает одну сессию.

```bash
curl http://127.0.0.1:8088/api/sessions/sess-...
```

### Запуски

#### `GET /api/runs`

Возвращает список запусков. По умолчанию возвращаются последние N запусков.

```bash
curl http://127.0.0.1:8088/api/runs
curl 'http://127.0.0.1:8088/api/runs?limit=50'
```

Все запуски:

```bash
curl 'http://127.0.0.1:8088/api/runs?all=true'
```

#### `GET /api/runs/{run_id}/summary`

Возвращает компактный результат запуска.

```bash
curl http://127.0.0.1:8088/api/runs/pipeline-.../summary
```

#### `GET /api/runs/{run_id}/steps`

Возвращает шаги pipeline с таймингами и usage, если usage доступен.

```bash
curl http://127.0.0.1:8088/api/runs/pipeline-.../steps
```

#### `GET /api/runs/{run_id}/checks`

Возвращает verification blocks и issues.

```bash
curl http://127.0.0.1:8088/api/runs/pipeline-.../checks
```

#### `GET /api/runs/{run_id}/diff`

Возвращает список измененных файлов и unified diff.

```bash
curl http://127.0.0.1:8088/api/runs/pipeline-.../diff
```

#### `GET /api/runs/{run_id}/code`

Возвращает generated code artifact и связанные сведения.

```bash
curl http://127.0.0.1:8088/api/runs/pipeline-.../code
```

#### `GET /api/runs/{run_id}/test`

Возвращает generated test artifact, если он был создан.

```bash
curl http://127.0.0.1:8088/api/runs/pipeline-.../test
```

#### `GET /api/runs/{run_id}/raw`

Возвращает raw JSON-артефакты запуска для отладки.

```bash
curl http://127.0.0.1:8088/api/runs/pipeline-.../raw
```

## Логирование и ошибки

`codeui` логирует:

- запуск приложения;
- вызовы CLI `codecollector`;
- рабочую директорию и команду;
- длительность выполнения команды;
- код возврата;
- размер stdout/stderr;
- ошибки чтения и записи JSON;
- создание, изменение и удаление CR;
- запуск анализа и обработки;
- применение результата к основному проекту;
- ошибки чтения run artifacts.

Большие JSON, diff, исходный код, prompt и raw output не должны выводиться в лог целиком. Для них логируются размеры, пути и короткие summary.

## Запуск и проверка

Установка и запуск:

```bash
cd /home/stickt/llm/codeui
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m codeui
```

Приложение доступно по адресу:

```text
http://127.0.0.1:8088/
```

Проверка Python-синтаксиса:

```bash
python -m compileall codeui
```

Проверка JavaScript-синтаксиса:

```bash
node --check codeui/static/app.js
```

## Текущие ограничения

- Аутентификация и авторизация не реализованы.
- Проекты не хранятся в `codeui`; список читается из `codecollector`.
- Требования подключаются как JSON-файл и не редактируются в UI.
- CR хранятся в JSON-файлах.
- Общее состояние UI хранится в JSON-файле.
- Pipeline выполняется в `codecollector`.
- Тяжелые run artifacts остаются в `.runs` проекта `codecollector`.
- Применение результата выполняется только после отдельного решения пользователя.
- Настройки моделей, prompt budget, reference library и verification pipeline находятся вне `codeui`.
