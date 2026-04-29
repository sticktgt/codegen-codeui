# AGENTS.md — контекст для агента Codex по проекту codeui

## Назначение проекта

`codeui` — отдельный web-проект для управления workflow вокруг `codecollector` через FastAPI и компактный HTML/JS/CSS-интерфейс.

Проект предназначен для аналитика или разработчика, который работает с требованиями, создает запросы на изменение кода, запускает анализ, выбирает место изменения, запускает обработку и принимает решение о применении результата в основной код.

`codeui` не заменяет `codecollector` и `codegenerator`:

- `codecollector` отвечает за техническую оркестрацию: проекты, сессии, анализ, выбор target, запуск pipeline, staging workspace, проверки и apply.
- `codegenerator` отвечает за генерацию кода, тестов и repair по структурированному запросу.
- `codeui` отвечает за UI/API-фасад, состояние пользовательского workflow, компактные представления результатов и связь CR с требованиями и запусками.

## Расположение проектов

Ожидаемая локальная структура:

```text
/home/stickt/llm/codecollector
/home/stickt/llm/codegenerator
/home/stickt/llm/codeui
```

`codeui/config.yaml` по умолчанию ожидает, что `codecollector` находится рядом:

```yaml
codecollector:
  root_dir: "../codecollector"
```

## Основной workflow UI

Текущий пользовательский порядок работы:

1. Выбрать проект.
2. Подключить JSON-файл требований.
3. Выбрать требование.
4. Создать CR, связанный с требованием.
5. Выполнить анализ CR.
6. Посмотреть кандидатов места изменения.
7. Выбрать место изменения человеком из списка кандидатов или ввести qualname вручную.
8. Запустить обработку.
9. Посмотреть результат: summary, шаги, проверки, diff, сгенерированный код, тест, raw JSON при необходимости.
10. Принять решение о применении результата в основной проект.

Финальный статус CR — только `applied`. Статус `ready_for_merge_review` не является финальным: из него можно редактировать CR и запускать pipeline заново.

## Важные правила разработки

1. По возможности менять только проект `codeui`.
2. `codecollector` менять только если без этого невозможно сделать нормальный UI/API workflow.
3. Совместимость с предыдущими версиями `codeui` не требуется.
4. README.md должен описывать только текущее состояние проекта as-is. Не добавлять историю изменений, changelog, сравнения с предыдущими версиями или описания инкрементов.
5. Все настройки, пути, команды, лимиты и константы должны задаваться через `config.yaml` или соответствующие поля конфигурации.
6. Пользовательское состояние UI, например выбранный проект, путь к требованиям, выбранный CR, хранится в `data/ui_state.json`, а не в `config.yaml`.
7. CR хранится как JSON в `data/change_requests/`.
8. Тяжелые артефакты pipeline не копировать в `codeui`; читать их из `.runs` проекта `codecollector`.
9. Не выводить весь `pipeline_run_*.json` как основной экран. Raw JSON допустим только как дополнительная опция.
10. Обязательно сохранять обработку ошибок и логирование для действий, запускающих команды или читающих артефакты.

## UI-правила

Интерфейс должен быть компактным и похожим на рабочее desktop/form-приложение.

Правила:

- использовать русский язык для пользовательских названий;
- избегать больших презентационных заголовков;
- не выравнивать рабочие значения по центру;
- значения полей выравнивать по левому краю рядом с подписями;
- raw JSON показывать только как дополнительный режим просмотра;
- внутренние термины заменять на пользовательские, где это возможно:
  - target → место изменения;
  - pipeline → обработка;
  - workspace → рабочая копия / результат применения;
  - merge/apply → применить результат.

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

Ключевые backend-файлы:

```text
codeui/main.py
codeui/config.py
codeui/errors.py
codeui/dependencies.py
codeui/api/routes_*.py
codeui/services/codecollector_client.py
codeui/services/command_runner.py
codeui/services/change_request_service.py
codeui/services/requirements_service.py
codeui/services/run_artifact_service.py
codeui/services/run_view_service.py
codeui/services/ui_state_service.py
codeui/services/json_io.py
```

Ключевые frontend-файлы:

```text
codeui/static/index.html
codeui/static/styles.css
codeui/static/app.js
```

## Конфигурация

Основной файл настроек:

```text
config.yaml
```

В нем задаются:

- имя и версия приложения;
- параметры HTTP-сервера;
- логирование;
- путь к `codecollector`;
- относительные пути `.runs`, `.state`, `.workspaces` внутри `codecollector`;
- директория хранения CR;
- дефолтный источник требований;
- UI-настройки, например количество последних запусков.

Не переносить в `codeui` настройки моделей, prompt budget, reference library и verification pipeline. Они относятся к `codecollector`/`codegenerator`.

## Состояние UI

Текущее пользовательское состояние хранится в:

```text
data/ui_state.json
```

Обычно там находятся:

```json
{
  "selected_project_id": "proj-...",
  "requirements_file_path": "data/requirements.json",
  "selected_requirement_ids": ["REQ-..."],
  "selected_change_request_id": "cr-..."
}
```

## Требования

`codeui` читает требования из JSON-файла. Поддерживаемый формат — объект с массивом `requirements`:

```json
{
  "requirements": [
    {
      "id": "LLM-A-000011",
      "type": "BR",
      "description": "...",
      "parent_id": null,
      "status": "новое",
      "verification_status": "верифицировано"
    }
  ]
}
```

Требования read-only. `codeui` их не редактирует.

Иерархия строится по `parent_id`. Если `title` отсутствует, отображаемый заголовок строится из начала `description`.

## Change Request / CR

CR — сущность `codeui`, которая связывает требования, выбранный проект, пользовательское описание изменения, сессию `codecollector` и запуски pipeline.

CR хранится в:

```text
data/change_requests/*.json
```

Важные поля CR:

```json
{
  "cr_id": "cr-...",
  "code": "CR-000001",
  "project_id": "proj-...",
  "requirement_id": "REQ-...",
  "requirement_ids": ["REQ-..."],
  "requirements_snapshot": [],
  "title": "...",
  "description": "...",
  "constraints": [],
  "requested_operation": "replace_symbol",
  "status": "draft",
  "session_id": null,
  "selected_target": null,
  "run_ids": [],
  "last_run_id": null,
  "last_workspace_id": null
}
```

`code` — короткий пользовательский идентификатор, например `CR-000001`. `cr_id` — технический идентификатор.

`requirements_snapshot` нужен, чтобы CR можно было открыть даже если исходный файл требований больше недоступен.

## Статусы CR

Используемые статусы:

- `draft` — запрос создан, анализ не выполнен или данные изменены;
- `analyzed` — анализ выполнен, есть кандидаты места изменения;
- `target_selected` — место изменения выбрано;
- `running` — выполняется действие или обработка;
- `ready_for_merge_review` — результат готов к ручной оценке и применению;
- `verification_failed` — проверки не прошли;
- `generated_test_verification_failed` — основной код прошел проверки, но проблема в generated test;
- `failed` — ошибка выполнения;
- `applied` — результат применен к основному проекту.

Только `applied` считается финальным статусом. Для `applied` запрещены analyze, select target, run, edit, delete и repeat apply.

## Связь CR с запусками

CR содержит `run_ids` и `last_run_id`.

Экран CR показывает только запуски, связанные с выбранным CR. Экран всех запусков показывает последние N запусков и может загрузить конкретный run напрямую при переходе из CR.

Применять результат можно только для последнего запуска CR и только если CR не `applied`.

## Интеграция с codecollector

`codeui` вызывает `codecollector` через CLI-wrapper в `codecollector_client.py` и `command_runner.py`.

Основные команды:

```bash
python -m codecollector projects list
python -m codecollector projects register ...
python -m codecollector sessions analyze ...
python -m codecollector sessions select-target ...
python -m codecollector sessions generate ...
python -m codecollector workspaces apply ...
```

CLI-команды должны логироваться без больших payload и без секретов.

## Run artifacts

`codeui` читает результаты из `.runs` проекта `codecollector`:

```text
codecollector/.runs/pipeline-.../
  pipeline_run_*.json
  generation_request.json
  generation_result.json
  generation_test_request.json
  generation_test_result.json
  repair_request.json
  repair_result.json
```

Основной UI должен показывать компактные view-models:

- результат;
- шаги с таймингами и токенами;
- проверки и проблемы;
- diff;
- сгенерированный код;
- сгенерированный тест;
- raw JSON как дополнительная опция.

## Отображение ошибок проверок

В `verification_report.blocks[].issues` элементы могут быть объектами, а не строками. Нельзя выводить их напрямую через `join`, иначе появится `[object Object]`.

Для issue показывать:

- `code`;
- `severity`;
- `message`;
- `file_path`;
- `symbol`, если есть.

`details` показывать в раскрываемом блоке.

## API

Основные группы API:

```text
/api/health
/api/settings
/api/projects
/api/ui-state
/api/requirements
/api/change-requests
/api/sessions
/api/runs
/api/workspaces
```

При ошибках использовать единый формат:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}
```

## Логирование и ошибки

Логировать:

- запуск приложения;
- чтение конфигурации;
- вызовы CLI-команд;
- длительность команд;
- return code;
- ошибки чтения/записи JSON;
- ошибки чтения run artifacts;
- apply workspace.

Не логировать целиком большие JSON, diff, исходный код, prompt или raw output. Вместо этого логировать размеры, пути и короткие summary.

## Команды разработки

Запуск:

```bash
cd /home/stickt/llm/codeui
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m codeui
```

Проверки Python-синтаксиса:

```bash
python -m compileall codeui
```

Проверка JavaScript-синтаксиса:

```bash
node --check codeui/static/app.js
```

## Ограничения текущего состояния

- Аутентификации и авторизации нет.
- Требования только читаются из JSON-файла.
- CR хранятся в JSON-файлах.
- Pipeline вызывается через CLI `codecollector`.
- Основной экран показывает компактные представления run artifacts, не полный `pipeline_run_*.json`.
- `codeui` не управляет настройками моделей, prompt budget и verification pipeline.
