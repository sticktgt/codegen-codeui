# AGENTS.md — контекст для агента по проекту codeui

## Назначение

`codeui` — отдельный web-проект для управления пользовательским workflow вокруг изменения кода через `codecollector`.

Проект предоставляет FastAPI API и компактный HTML/JS/CSS-интерфейс. Пользователь работает с проектами, требованиями, запросами на изменение, анализом, выбором места изменения, запуском обработки и применением результата.

`codeui` не реализует собственный pipeline изменения кода. Он вызывает `codecollector`, хранит собственные CR, связывает CR с требованиями и запусками, а также отображает compact view по run artifacts.

## Границы ответственности

`codeui` отвечает за:

- web UI;
- FastAPI endpoints;
- пользовательское состояние UI;
- подключение файла требований;
- отображение дерева требований;
- создание, редактирование и удаление CR;
- хранение snapshot требований в CR;
- связь CR с запусками;
- вызовы `codecollector` через CLI-wrapper;
- отображение результатов analyze;
- отображение run artifacts в компактном виде;
- apply последнего результата CR по решению пользователя.

`codeui` не отвечает за:

- индексирование проекта;
- поиск символов внутри проекта;
- построение context pack;
- prompt assembly;
- вызов LLM для генерации кода;
- применение patch в staging workspace;
- verification pipeline.

Эти действия выполняются вне `codeui`. В `codeui` они видны через CLI-вызовы и JSON-артефакты.

## Расположение

Ожидаемая локальная структура:

```text
/home/stickt/llm/codecollector
/home/stickt/llm/codegenerator
/home/stickt/llm/codeui
```

`codeui/config.yaml` по умолчанию ожидает соседний каталог `../codecollector`.

## Основной workflow

1. Выбрать проект.
2. Подключить JSON-файл требований.
3. Выбрать требование.
4. Создать CR.
5. Выполнить анализ CR.
6. Посмотреть качество запроса, операцию, рекомендацию места изменения и кандидатов.
7. Выбрать место изменения из кандидатов или ввести qualname вручную.
8. Запустить обработку.
9. Посмотреть результат запуска.
10. Применить последний результат к основному проекту отдельным решением пользователя.

Финальный статус CR — только `applied`.

## Правила разработки

- Документация пишется только на русском языке.
- README.md описывает только текущее состояние проекта.
- Не добавлять changelog, историю инкрементов и сравнения со старыми реализациями.
- Не сохранять совместимость со старыми версиями, если это мешает текущей задаче.
- Предпочитать простые изменения сложным перестройкам.
- Не добавлять зависимости без явной необходимости.
- Настройки, пути, лимиты и константы держать в `config.yaml` или в конфигурационных схемах, а не размазывать по коду.
- Пользовательское состояние хранить в `data/ui_state.json`, а не в `config.yaml`.
- CR хранить в `data/change_requests/*.json`.
- Тяжелые run artifacts не копировать в `codeui`; читать их из `.runs` проекта `codecollector`.
- Raw JSON не должен быть основным экраном, только дополнительной опцией.
- Любые действия, вызывающие CLI или читающие артефакты, должны иметь обработку ошибок и логирование.

## UI-правила

Интерфейс должен быть компактным рабочим приложением, похожим на desktop/form UI.

Правила:

- использовать русский язык;
- избегать больших презентационных заголовков;
- не выравнивать рабочие значения по центру;
- значения показывать рядом с подписями, по левому краю;
- не дублировать одни и те же поля в нескольких крупных блоках;
- raw JSON показывать только как дополнительный режим;
- внутренние термины по возможности переводить:
  - target → место изменения;
  - anchor → anchor или место вставки, если это важно для смысла;
  - pipeline → обработка;
  - workspace → рабочая копия;
  - apply → применить результат.

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

Основные backend-файлы:

```text
codeui/main.py
codeui/__main__.py
codeui/config.py
codeui/dependencies.py
codeui/errors.py
codeui/logger.py
codeui/api/routes_*.py
codeui/schemas/*.py
codeui/services/codecollector_client.py
codeui/services/command_runner.py
codeui/services/change_request_service.py
codeui/services/requirements_service.py
codeui/services/run_artifact_service.py
codeui/services/run_view_service.py
codeui/services/ui_state_service.py
codeui/services/json_io.py
```

Основные frontend-файлы:

```text
codeui/static/index.html
codeui/static/styles.css
codeui/static/app.js
```

## Конфигурация и состояние

Основная конфигурация находится в `config.yaml`.

В конфигурации задаются:

- имя и версия приложения;
- параметры сервера;
- логирование;
- путь к `codecollector`;
- команда запуска `codecollector`;
- timeout CLI-команд;
- пути `.runs`, `.state`, `.workspaces` внутри `codecollector`;
- дефолтный источник требований;
- директория хранения CR;
- UI-настройки.

Текущее состояние UI хранится в `data/ui_state.json`. Обычно там находятся:

```json
{
  "selected_project_id": "proj-...",
  "requirements_file_path": "data/requirements.json",
  "selected_requirement_ids": ["REQ-..."],
  "selected_change_request_id": "cr-..."
}
```

## Требования

`codeui` читает требования из JSON-файла. Требования не редактируются.

Поддерживается объект с массивом `requirements` или список требований на верхнем уровне.

Иерархия строится по `parent_id`. Если `title` отсутствует, заголовок строится из начала `description`.

При создании CR связанные требования сохраняются в `requirements_snapshot`, чтобы CR можно было открыть даже при недоступном или измененном файле требований.

## Change Request

CR — основная сущность `codeui`.

CR связывает:

- проект;
- требования;
- пользовательское описание изменения;
- ручную или автоматически рекомендованную операцию;
- сессию анализа;
- выбранное место изменения;
- список запусков;
- последний run и workspace;
- факт применения результата.

Важные поля CR:

```json
{
  "cr_id": "cr-...",
  "code": "CR-000001",
  "project_id": "proj-...",
  "requirement_ids": ["REQ-..."],
  "requirements_snapshot": [],
  "title": "...",
  "description": "...",
  "constraints": [],
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

`requested_operation` — ручной выбор пользователя. Если значение `null`, analyze вызывается без operation.

`raw.last_analyze_result` содержит последний ответ analyze и используется для отображения качества запроса, операции, рекомендации места изменения, кандидатов, предупреждений и статистики.

## Статусы CR

- `draft` — запрос создан или изменен;
- `analyzed` — анализ выполнен;
- `needs_user_decision` — требуется выбор пользователя;
- `analysis_insufficient` — запрос недостаточно конкретный;
- `target_selected` — место изменения выбрано;
- `running` — выполняется действие;
- `ready_for_merge_review` — результат готов к ручной проверке;
- `verification_failed` — проверки не прошли;
- `generated_test_verification_failed` — проблема только в generated test;
- `failed` — ошибка выполнения;
- `applied` — результат применен к основному проекту.

Только `applied` является финальным статусом. Для `applied` запрещены edit, delete, analyze, select target, run и repeat apply.

`ready_for_merge_review` не финальный. Из него можно изменить CR и запустить обработку заново.

## Analyze contract

Analyze может выполняться без operation. В этом случае operation определяет `codecollector`.

Ключевые поля analyze:

```json
{
  "requested_operation": "replace_symbol",
  "operation_source": "llm_search_plan",
  "operation_confidence": 0.6,
  "operation_reason": "...",
  "request_quality": {
    "status": "processable",
    "reason": "...",
    "missing_information": []
  },
  "target_recommendation": {
    "recommended_target": "...",
    "target_role": "target",
    "target_confidence": 0.95,
    "target_reason": "...",
    "manual_review_required": false,
    "warnings": []
  },
  "analysis_usage": {
    "calls": 2,
    "prompt_tokens": 5006,
    "output_tokens": 874,
    "total_tokens": 5880,
    "prompt_chars": 19496,
    "duration_sec": 24.82
  },
  "result_summary": {
    "status": "analyzed",
    "request_quality_status": "processable",
    "manual_review_required": false
  }
}
```

`request_quality.status`:

- `processable` — можно продолжать workflow;
- `uncertain` — можно продолжать с предупреждением;
- `insufficient` — нельзя запускать обработку, нужно изменить CR и выполнить analyze заново.

`operation_source`:

- `user` — операция выбрана пользователем;
- `llm_search_plan` — операция выбрана LLM на этапе плана поиска;
- `llm_rerank` — операция уточнена LLM после кандидатов;
- `fallback` — надежной операции нет, нужен ручной выбор.

Если `operation_source = fallback`, UI не должен считать operation надежно выбранной.

Для `insert_after_symbol` поле `target_role = anchor` означает, что выбранный symbol является местом, после которого будет вставлен новый код.

## Run artifacts

Run artifacts читаются из `.runs` проекта `codecollector`.

Важные файлы:

```text
pipeline_run_*.json
generation_request.json
generation_result.json
generation_test_request.json
generation_test_result.json
repair_request.json
repair_result.json
```

Основной UI показывает compact view:

- результат;
- план применения;
- шаги;
- проверки;
- статистика;
- diff;
- код;
- тест;
- JSON как дополнительная опция.

## Отображение ошибок проверок

`verification_report.blocks[].issues` может содержать объекты.

Нельзя выводить объект напрямую в DOM. Нужно форматировать поля:

- `code`;
- `severity`;
- `message`;
- `file_path`;
- `symbol`;
- `details` в раскрываемом блоке.

## API-группы

Основные группы endpoint-ов:

```text
/api/health
/api/settings
/api/ui-state
/api/projects
/api/requirements
/api/change-requests
/api/sessions
/api/runs
/api/workspaces
```

Ключевые action endpoint-ы:

```text
POST /api/change-requests/{cr_id}/analyze
POST /api/change-requests/{cr_id}/select-target
POST /api/change-requests/{cr_id}/run
POST /api/change-requests/{cr_id}/apply-last-run
```

Ошибки возвращаются в формате:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}
```

## Интеграция с codecollector

Вызовы `codecollector` выполняются через `CodecollectorClient` и `CommandRunner`.

Команды:

```bash
python -m codecollector projects list
python -m codecollector projects register ...
python -m codecollector sessions analyze ...
python -m codecollector sessions select-target ...
python -m codecollector sessions generate ...
python -m codecollector workspaces apply ...
```

CLI-вызовы должны логироваться с cwd, command, duration, returncode и размерами stdout/stderr. Не логировать большие payload целиком.

## Логирование и ошибки

Логировать:

- старт приложения;
- чтение конфигурации;
- вызовы CLI;
- длительность CLI-команд;
- return code;
- ошибки JSON I/O;
- создание, изменение и удаление CR;
- analyze, select-target, run, apply;
- ошибки чтения run artifacts.

При ошибках API использовать единый формат из `errors.py`.

## Команды проверки

Запуск:

```bash
cd /home/stickt/llm/codeui
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m codeui
```

Проверка Python:

```bash
python -m compileall codeui
```

Проверка JavaScript:

```bash
node --check codeui/static/app.js
```

## Ограничения

- Аутентификации и авторизации нет.
- Требования read-only и подключаются из JSON.
- CR хранятся в JSON-файлах.
- UI-состояние хранится в JSON-файле.
- Pipeline выполняется в `codecollector`.
- Run artifacts остаются в `.runs` проекта `codecollector`.
- Настройки моделей, prompt budget, reference library и verification pipeline не управляются из `codeui`.
