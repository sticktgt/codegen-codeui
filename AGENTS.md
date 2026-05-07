# AGENTS.md — контекст для агента по проекту codeui

## Назначение

`codeui` — отдельный web-проект для управления workflow вокруг `codecollector` через FastAPI и компактный HTML/JS/CSS-интерфейс.

Проект предназначен для аналитика или разработчика, который работает с требованиями, создает запросы на изменение кода, запускает анализ, выбирает место изменения, запускает обработку и принимает решение о применении результата в основной код.

`codeui` не заменяет `codecollector` и `codegenerator`. Он отвечает за UI/API-фасад, состояние пользовательского workflow, компактные представления результатов и связь CR с требованиями и запусками.

## Границы ответственности

`codeui` отвечает за:

- выбор проекта;
- подключение файла требований;
- отображение требований;
- создание и хранение CR;
- связь CR с требованиями и запусками;
- вызовы `codecollector` через CLI;
- отображение результатов analyze;
- отображение target/anchor/parent class и insert scope;
- запуск обработки;
- отображение run artifacts;
- отображение verification, generated tests, import changes, diff и статистики;
- apply последнего результата по решению пользователя.

`codeui` не отвечает за:

- индексирование проекта;
- поиск символов внутри кода;
- сбор context pack;
- prompt assembly;
- вызов LLM;
- patching внутри staging workspace;
- verification pipeline;
- генерацию кода или тестов.

Эти задачи остаются в `codecollector` и `codegenerator`.

## Расположение

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

## Основной workflow

Текущий пользовательский порядок работы:

1. Выбрать проект.
2. Подключить JSON-файл требований.
3. Выбрать требование.
4. Создать CR, связанный с требованием.
5. Выполнить анализ CR.
6. Посмотреть качество запроса, рекомендованную операцию, область вставки и рекомендацию места изменения.
7. Посмотреть кандидатов места изменения.
8. Выбрать место изменения человеком из списка кандидатов или ввести qualname вручную.
9. Запустить обработку.
10. Посмотреть результат: summary, шаги, проверки, diff, generated code, generated test, import changes, warnings и статистику.
11. Принять решение о применении результата в основной проект.

Финальный статус CR — только `applied`. Статус `ready_for_merge_review` не является финальным: из него можно редактировать CR и запускать pipeline заново.

## Правила разработки

1. По возможности менять только проект `codeui`.
2. `codecollector` менять только если без этого невозможно сделать нормальный UI/API workflow.
3. Совместимость с предыдущими версиями `codeui` не требуется.
4. README.md должен описывать только текущее состояние проекта as-is. Не добавлять историю изменений, changelog, сравнения с предыдущими версиями или описания инкрементов.
5. Все настройки, пути, команды, лимиты и константы задаются через `config.yaml` или соответствующие поля конфигурации.
6. Пользовательское состояние UI, например выбранный проект, путь к требованиям и выбранный CR, хранится в `data/ui_state.json`, а не в `config.yaml`.
7. CR хранится как JSON в `data/change_requests/`.
8. Тяжелые артефакты pipeline не копируются в `codeui`; они читаются из `.runs` проекта `codecollector`.
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
- не скрывать важные технические статусы, но объяснять их понятным языком;
- внутренние термины заменять на пользовательские, где это возможно:
  - target → место изменения;
  - anchor → точка вставки;
  - parent class → родительский класс;
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
codeui/api/routes_change_requests.py
codeui/api/routes_projects.py
codeui/api/routes_requirements.py
codeui/api/routes_runs.py
codeui/api/routes_ui_state.py
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

## Конфигурация и состояние

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
- timeout CLI-команд;
- директория хранения CR;
- дефолтный источник требований;
- UI-настройки, например количество последних запусков.

Не переносить в `codeui` настройки моделей, prompt budget, reference library и verification pipeline. Они относятся к `codecollector`/`codegenerator`.

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

`codeui` читает требования из JSON-файла. Поддерживаемый формат — объект с массивом `requirements` или список требований на верхнем уровне.

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
  "notes": [],
  "requested_operation": null,
  "insert_scope": null,
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

`code` — короткий пользовательский идентификатор. `cr_id` — технический идентификатор.

`requirements_snapshot` нужен, чтобы CR можно было открыть даже если исходный файл требований больше недоступен.

`requested_operation` — ручной выбор пользователя. Поле может быть `null`: тогда analyze вызывается без operation, а `codecollector` пытается определить операцию автоматически.

`insert_scope` используется для `insert_after_symbol`:

- `module_body` — добавление top-level функции или класса в модуль;
- `class_body` — добавление метода внутрь класса;
- пусто — не применимо или еще не определено.

Результат анализа сохраняется в `raw.last_analyze_result` и включает request quality, operation source/confidence/reason, insert scope, target recommendation, LLM-rerank кандидатов и usage.

Если `operation_source = fallback`, операция не считается надежно выбранной, и UI должен требовать ручной выбор операции перед select-target/generate.

Если `request_quality.status = insufficient`, UI не должен разрешать generate и не должен предлагать select-target как обход. Правильный путь — изменить поля CR и выполнить analyze заново.

## Статусы CR

Используемые статусы:

- `draft` — запрос создан, анализ не выполнен или данные изменены;
- `analyzing` — выполняется анализ;
- `analyzed` — анализ выполнен, есть рабочая рекомендация или кандидаты места изменения;
- `needs_user_decision` — анализ выполнен, но требуется ручной выбор target/anchor/parent class или уточнение действия;
- `analysis_insufficient` — запрос недостаточно конкретный, генерация заблокирована до редактирования CR и повторного анализа;
- `selecting_target` — выполняется выбор места изменения;
- `target_selected` — место изменения выбрано;
- `running` — выполняется действие или обработка;
- `ready_for_merge_review` — результат готов к ручной оценке и применению;
- `verification_failed` — production/runtime проверки не прошли;
- `generated_test_verification_failed` — production-код можно рассматривать для review, но generated test не прошел проверку;
- `repair_verification_failed` — repair был выполнен, но проверки не прошли;
- `repair_no_effective_change` — repair не дал полезного изменения;
- `failed` — ошибка выполнения;
- `applied` — результат применен к основному проекту.

Только `applied` считается финальным статусом. Для `applied` запрещены analyze, select target, run, edit, delete и repeat apply.

## Analyze contract

Analyze может определить operation и insert scope автоматически.

Основные поля результата:

```json
{
  "session_id": "sess-...",
  "project_id": "proj-...",
  "requested_operation": "insert_after_symbol",
  "insert_scope": "class_body",
  "operation_source": "llm_rerank",
  "operation_confidence": 0.95,
  "operation_reason": "...",
  "request_quality": {
    "status": "processable",
    "reason": "...",
    "missing_information": []
  },
  "target_recommendation": {
    "recommended_target": "support_app.storage.ticket_repository.TicketRepository",
    "target_role": "parent_class",
    "target_confidence": 1.0,
    "target_reason": "...",
    "manual_review_required": false,
    "warnings": []
  },
  "candidates": [],
  "analysis_usage": {},
  "result_summary": {
    "status": "analyzed",
    "requested_operation": "insert_after_symbol",
    "insert_scope": "class_body",
    "recommended_target": "support_app.storage.ticket_repository.TicketRepository",
    "manual_review_required": false,
    "request_quality_status": "processable",
    "target_selection_confidence": 1.0
  }
}
```

`request_quality.status`:

- `processable` — запрос достаточно конкретный;
- `uncertain` — можно продолжать, но нужно предупреждение;
- `insufficient` — нельзя запускать generate, нужно переписать CR.

`result_summary.status`:

- `analyzed` — система дала рабочую рекомендацию;
- `needs_user_decision` — требуется ручное действие пользователя.

`needs_user_decision` не является ошибкой само по себе. Его нужно интерпретировать вместе с `request_quality.status`, `manual_review_required`, `recommended_target` и `target_recommendation`.

## Operation, insert scope и target role

Поддерживаемые операции:

- `replace_symbol` — заменить существующий символ;
- `insert_after_symbol` — вставить новый код относительно существующего символа или внутрь класса.

Поддерживаемые `insert_scope`:

- `module_body` — добавление top-level функции или класса в модуль;
- `class_body` — добавление метода внутрь класса;
- пусто — не применимо для `replace_symbol` или еще не определено.

Поддерживаемые роли:

- `target` — символ будет заменен;
- `anchor` — символ используется как точка вставки;
- `parent_class` — класс, внутрь которого будет добавлен новый метод;
- `unknown` — место изменения не определено.

Нельзя смешивать target, anchor и parent class. Для `class_body` выбранный symbol является родительским классом. Для `module_body` выбранный symbol является anchor для вставки после него.

## Кандидаты места изменения

Кандидат может содержать:

```json
{
  "qualname": "support_app.services.report_service.build_priority_label",
  "name": "build_priority_label",
  "kind": "function",
  "file_path": "support_app/services/report_service.py",
  "score": 17.82,
  "confidence": 0.93,
  "relevance_category": "высокая",
  "reasons": [],
  "docstring": "...",
  "knowledge_title": "...",
  "requirements": [],
  "ranked_by_llm": true,
  "llm_recommended": true,
  "llm_rank": 1,
  "llm_reason": "..."
}
```

Если `ranked_by_llm = false`, кандидат не должен отображаться как оцененный LLM. Для него используется метка “не ранжировался LLM”.

## Select target

Select target фиксирует выбранное место изменения в сессии `codecollector`.

Для `insert_after_symbol` вместе с qualname передаются operation и insert scope.

CLI-аналог:

```bash
python -m codecollector sessions select-target \
  --session-id sess-... \
  --selected-qualname support_app.storage.ticket_repository.TicketRepository \
  --operation insert_after_symbol \
  --insert-scope class_body
```

Если CR находится в состоянии `analysis_insufficient`, select-target не должен использоваться как обход. Нужно изменить CR и выполнить analyze заново.

## Generate

Generate запускает `sessions generate` в `codecollector`.

Генерация разрешена, если:

- CR не `applied`;
- request quality не `insufficient`;
- выбрана надежная operation;
- если operation `insert_after_symbol`, выбран `insert_scope`;
- есть selected target или надежно рекомендованный target;
- сессия готова к генерации.

Если generate возвращает `generation_blocked = true`, UI показывает это как нормальное состояние, а не как crash.

Для `block_reason = insufficient_request` UI показывает, что запрос недостаточно конкретен и его нужно переписать.

Для `block_reason = session_not_ready` UI показывает, что сессия не готова к генерации и нужно выбрать target/anchor/parent class или выполнить analyze заново.

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

Основной UI показывает compact view-models:

- результат;
- шаги с таймингами и токенами;
- проверки и проблемы;
- план применения;
- diff;
- import changes;
- сгенерированный код;
- сгенерированный тест;
- raw JSON как дополнительная опция.

## Import changes

`codegenerator` может вернуть `import_changes` внутри `code_artifact`, а `codecollector` применяет их к target file.

UI показывает import changes в составе code artifact и плана применения. В diff они отображаются как обычное изменение файла. Пользователь не выполняет отдельную операцию для imports.

Не хардкодить import changes под конкретный пример. Нужно отображать structured import changes, если они есть, и diff как есть.

## Verification

В `verification_report.blocks[]` показывать каждый блок:

- `name`;
- `ok`;
- `severity`;
- `issues`;
- `details` по раскрытию.

Основные блоки:

- `patch_static_semantics`;
- `generated_test_static_semantics`;
- `generated_test_relevance`;
- `runtime_ast_parse`;
- `runtime_py_compile`;
- `runtime_pytest_recommended`.

Если `ok = false`, issues выводятся крупно и понятно.

Элементы `issues` могут быть объектами, а не строками. Нельзя выводить их напрямую через `join`, иначе появится `[object Object]`.

Для issue показывать:

- `code`;
- `severity`;
- `message`;
- `file_path`;
- `symbol`, если есть.

## Generated test

Если `has_generated_test = true`, UI показывает:

- список generated test files;
- test artifact source, если он доступен;
- verification blocks, связанные с generated test;
- статус `generated_test_apply`.

Если generated test создан, но не прошел verification, статус запуска может быть `generated_test_verification_failed`. Это не равно обычному production failure.

Для такого результата UI показывает:

- production-код можно рассматривать для review;
- generated test не прошел проверку;
- generated test может быть исключен из apply;
- apply разрешается только если merge plan готов к ручному применению.

Если test generation не вернул artifact, UI показывает warning, а не считает это обычной ситуацией “тестов нет”.

## Статистика

Для analyze UI показывает `analysis_usage`:

- calls;
- prompt tokens;
- output tokens;
- total tokens;
- prompt chars;
- duration sec;
- steps.search_plan;
- steps.candidate_rerank;
- timings.

Для pipeline/codegenerator UI показывает usage из:

- `external_code_generation.result_summary.llm_usage`;
- `external_test_generation.result_summary.llm_usage`;
- `repair_generation.result_summary.llm_usage`, если есть.

Также UI показывает prompt/context metrics, если они есть:

- request chars;
- target source chars;
- related test chars;
- reference chars;
- full file included;
- trim steps.

## API-группы

Основные группы API:

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

CLI-команды логируются без больших payload и без секретов.

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

## Что нельзя делать

- Не хардкодить demo-project-specific qualnames.
- Не скрывать технические статусы.
- Не считать `needs_user_decision` ошибкой.
- Не запускать generate для `insufficient_request`.
- Не использовать select-target как исправление недостаточного запроса.
- Не смешивать значения target, anchor и parent class.
- Не считать `generated_test_verification_failed` обычной production-поломкой.
- Не считать excluded files ошибкой apply.
- Не выводить object issues как строку.
- Не переносить настройки моделей, prompt budget и verification pipeline в `codeui`.

## Команды проверки

Запуск:

```bash
cd /home/stickt/llm/codeui
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m codeui
```

Проверка Python-синтаксиса:

```bash
python -m compileall codeui
```

Проверка JavaScript-синтаксиса:

```bash
node --check codeui/static/app.js
```

## Ограничения

- Аутентификация и авторизация не реализованы.
- Требования только читаются из JSON-файла.
- CR хранятся в JSON-файлах.
- Pipeline вызывается через CLI `codecollector`.
- Основной экран показывает compact view, а не полный `pipeline_run_*.json`.
- `codeui` не управляет настройками моделей, prompt budget и verification pipeline.
