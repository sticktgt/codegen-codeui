# codeui

`codeui` — веб-интерфейс и FastAPI-фасад для управляемой работы с `codecollector`.

Приложение предназначено для рабочего сценария, в котором пользователь выбирает проект, подключает файл требований, создает запрос на изменение кода, выполняет анализ, выбирает место изменения, запускает обработку, просматривает результат и принимает решение о применении изменений к основному проекту.

`codeui` не выполняет генерацию и не изменяет код напрямую. Технический pipeline выполняет `codecollector`; `codeui` хранит пользовательские запросы, вызывает `codecollector` через CLI, отображает компактные представления JSON-артефактов и помогает человеку принять решение.

## Основной сценарий работы

1. Выбрать проект.
2. Подключить JSON-файл требований.
3. Выбрать требование.
4. Создать запрос на изменение.
5. Выполнить анализ запроса.
6. Проверить качество запроса, операцию, область вставки и рекомендацию места изменения.
7. Выбрать место изменения из кандидатов или ввести его вручную.
8. Запустить обработку.
9. Просмотреть результат, шаги, проверки, diff, сгенерированный код, тест и статистику.
10. Применить результат к основному проекту отдельным решением пользователя.

## Текущий функционал

- Выбор проекта из списка проектов, зарегистрированных в `codecollector`; выбранное значение сохраняется при изменении списка.
- Добавление нового проекта через onboarding `codecollector projects onboard`.
- Сохранение выбранного проекта в UI-состоянии.
- Удаление проекта через `codecollector projects delete` после подтверждения пользователя.
- Подключение JSON-файла требований.
- Отображение требований иерархически по `parent_id`.
- Просмотр выбранного требования.
- Создание CR, связанного с одним или несколькими требованиями.
- Фильтрация списка CR по активному проекту `codecollector`.
- Хранение snapshot требований внутри CR.
- Короткий код CR вида `CR-000001`.
- Редактирование CR до применения результата к основному проекту.
- Удаление CR до применения результата к основному проекту.
- Анализ CR без обязательного ручного выбора операции.
- Отображение качества запроса, операции, области вставки, роли места изменения, рекомендации, предупреждений, кандидатов и статистики анализа.
- Ручной выбор операции, области вставки и места изменения.
- Поддержка ролей места изменения: `target`, `anchor`, `parent_class`, `unknown`.
- Блокировка обработки для недостаточного запроса.
- Запуск обработки через `codecollector`.
- Хранение связи CR с запусками pipeline.
- Просмотр запусков, связанных с выбранным CR.
- Просмотр общего списка запусков с ограничением по умолчанию и возможностью загрузить весь список.
- Фильтрация списка запусков по активному проекту через связь `CR.run_ids` / `CR.last_run_id`.
- Просмотр результата запуска: summary, шаги, проверки, план применения, статистика, diff, финальный production-код, тест.
- Отображение import changes, если они есть в code artifact или summary запуска.
- Отображение generated test, его статуса и excluded files.
- Отображение ошибок проверок с кодом, сообщением, файлом, символом и раскрываемыми деталями.
- Отображение финального production artifact после repair, если repair использовался.
- Применение последнего результата CR к основному проекту.

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
      __init__.py
      routes_change_requests.py
      routes_health.py
      routes_projects.py
      routes_requirements.py
      routes_runs.py
      routes_sessions.py
      routes_settings.py
      routes_ui_state.py
      routes_workspaces.py
    schemas/
      __init__.py
      change_requests.py
      common.py
      requirements.py
      runs.py
      settings.py
      ui_state.py
    services/
      __init__.py
      change_request_service.py
      codecollector_client.py
      command_runner.py
      json_io.py
      requirements_service.py
      run_artifact_service.py
      run_view_service.py
      ui_state_service.py
    static/
      index.html
      app.js
      styles.css
```

## Основные файлы

- `README.md` — описание текущего состояния проекта.
- `AGENTS.md` — краткий рабочий контекст для LLM-агента.
- `pyproject.toml` — пакетная конфигурация и зависимости.
- `config.yaml` — конфигурация приложения, путей и интеграции с `codecollector`.
- `data/ui_state.json` — текущее пользовательское состояние UI.
- `data/requirements.json` — пример или подключенный файл требований.
- `data/change_requests/` — JSON-файлы пользовательских запросов на изменение.
- `codeui/main.py` — создание FastAPI-приложения, регистрация маршрутов и static UI.
- `codeui/config.py` — загрузка `config.yaml`, вычисление рабочих путей.
- `codeui/errors.py` — единый формат API-ошибок.
- `codeui/dependencies.py` — создание и передача сервисов в API routes.
- `codeui/logger.py` — настройка логирования.
- `codeui/api/routes_change_requests.py` — API для CR, analyze, select-target, run и apply.
- `codeui/api/routes_projects.py` — API для чтения, onboarding и удаления проектов через `codecollector`.
- `codeui/api/routes_requirements.py` — API для чтения требований и дерева требований.
- `codeui/api/routes_runs.py` — API для просмотра run artifacts.
- `codeui/api/routes_ui_state.py` — API для текущего состояния UI.
- `codeui/services/change_request_service.py` — хранение CR, статусы, связь с analyze/run/apply.
- `codeui/services/codecollector_client.py` — CLI-wrapper для вызова `codecollector`.
- `codeui/services/command_runner.py` — запуск команд, timeout, stdout/stderr, логирование.
- `codeui/services/requirements_service.py` — чтение и нормализация требований.
- `codeui/services/run_artifact_service.py` — чтение run artifacts из `.runs`.
- `codeui/services/run_view_service.py` — compact view-models для запуска.
- `codeui/services/ui_state_service.py` — чтение и запись `data/ui_state.json`.
- `codeui/services/json_io.py` — безопасное чтение и запись JSON-файлов.
- `codeui/static/index.html` — HTML-структура UI.
- `codeui/static/app.js` — клиентская логика UI.
- `codeui/static/styles.css` — compact desktop-like оформление.

## Конфигурация

Основной файл настроек — `config.yaml`.

В нем задаются:

- имя приложения;
- параметры HTTP-сервера;
- уровень логирования;
- путь к `codecollector`;
- команда Python и module name для CLI-вызовов;
- относительные пути `.runs`, `.state`, `.workspaces` внутри `codecollector`;
- timeout команд;
- директория хранения CR;
- дефолтный источник требований;
- UI-настройки.

Пример:

```yaml
app:
  name: "codeui"
  version: "0.2.24"

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

Текущий выбор пользователя не хранится в `config.yaml`. Для этого используется `data/ui_state.json`.

Пример UI-состояния:

```json
{
  "selected_project_id": "proj-...",
  "requirements_file_path": "data/requirements.json",
  "selected_requirement_ids": ["REQ-..."],
  "selected_change_request_id": "cr-..."
}
```

## Требования

`codeui` читает требования из JSON-файла. Поддерживается объект с массивом `requirements` или список требований на верхнем уровне.

Пример:

```json
{
  "requirements": [
    {
      "id": "LLM-A-000011",
      "type": "BR",
      "status": "новое",
      "description": "Система должна автоматически проверять паспорт.",
      "parent_id": null,
      "verification_status": "верифицировано"
    }
  ]
}
```

Требования в `codeui` только читаются. Иерархия строится по `parent_id`. Если `title` отсутствует, заголовок строится из начала `description`.

Для отображения используются поля:

- `id`;
- `title`;
- `type`;
- `description`;
- `status`;
- `priority`;
- `parent_id`;
- `verification_status`;
- `note`;
- `created_at`;
- `project_id`;
- `acceptance_criteria`;
- `tags`;
- `user_roles`.

Если требование связано с CR, UI показывает связанные запросы и их актуальные статусы. При выбранном активном проекте основной список связанных CR показывает только запросы этого проекта. Если у видимого требования есть CR из других проектов, UI показывает отдельный раскрываемый блок с предупреждением, чтобы пользователь не смешивал работу по разным проектам.

## Запрос на изменение

CR хранится как JSON-файл в `data/change_requests/`.

Пример структуры:

```json
{
  "cr_id": "cr-20260504T155053968634Z-7d9bb3",
  "code": "CR-000009",
  "project_id": "proj-...",
  "requirement_id": "REQ-...",
  "requirement_ids": ["REQ-..."],
  "requirements_snapshot": [],
  "title": "Изменить текст уведомления",
  "description": "Сделать уведомление на русском языке.",
  "constraints": ["Не менять внешний контракт API"],
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

`code` — пользовательский короткий идентификатор. `cr_id` — технический идентификатор.

`requirements_snapshot` нужен для устойчивого отображения CR, если файл требований недоступен или требование удалено.

`requested_operation` может быть пустым. В этом случае `sessions analyze` вызывается без operation, а `codecollector` пытается определить операцию автоматически.

`insert_scope` используется для `insert_after_symbol` и определяет, куда вставляется новый код:

- `module_body` — добавление top-level функции или класса в модуль;
- `class_body` — добавление метода внутрь класса;
- пусто — не применимо или еще не определено.

Если `requested_operation = insert_after_symbol`, UI должен явно показывать `insert_scope`. Если `insert_scope` не определен, пользователь выбирает его перед ручным select-target или запуском обработки.

## Статусы CR

Используемые статусы:

- `draft` — запрос создан или отредактирован;
- `analyzing` — выполняется анализ;
- `analyzed` — анализ дал рабочую рекомендацию;
- `needs_user_decision` — требуется ручной выбор места изменения или уточнение;
- `analysis_insufficient` — запрос недостаточно конкретный;
- `selecting_target` — выполняется выбор места изменения;
- `target_selected` — место изменения выбрано;
- `running` — выполняется обработка;
- `ready_for_merge_review` — результат готов к ручной оценке и применению;
- `verification_failed` — production/runtime проверки не прошли;
- `generated_test_verification_failed` — production-код можно рассматривать для review, но generated test не прошел проверку;
- `repair_verification_failed` — repair был выполнен, но проверки не прошли;
- `repair_no_effective_change` — repair не дал полезного изменения;
- `failed` — ошибка выполнения;
- `applied` — результат применен к основному проекту.

Только `applied` считается финальным статусом. Для `applied` запрещены analyze, select target, run, edit, delete и повторный apply.

`ready_for_merge_review` не является финальным статусом. Из этого состояния можно изменить CR и выполнить обработку заново.

Список CR в UI фильтруется по выбранному проекту `codecollector`. Если проект не выбран, отображаются все CR. Фильтр использует поле `project_id` CR и не зависит от `project_id` внутри файла требований.

## Запуски

Список запусков фильтруется по активному проекту через CR, с которыми связаны run artifacts. `codeui` не пытается определять проект по содержимому run directory. Если запуск создан вне `codeui` и не связан ни с одним CR, он отображается в общем списке без выбранного проекта или открывается напрямую из известной ссылки/CR, но не используется для проектного фильтра.

## Analyze

Analyze запускает `sessions analyze` в `codecollector`.

Если пользователь не выбрал операцию, analyze вызывается без `--operation`.

Если пользователь выбрал операцию вручную, она передается явно.

Если операция `insert_after_symbol` и пользователь выбрал область вставки, передается `--insert-scope`.

Результат analyze сохраняется в `raw.last_analyze_result` CR.

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
    "target_selection_confidence": 1.0,
    "recall_candidates_count": 12,
    "returned_candidates_count": 5,
    "has_context_summary": true
  }
}
```

UI показывает:

- `session_id`;
- `project_id`;
- `result_summary.status`;
- `requested_operation`;
- `insert_scope`;
- `recommended_target`;
- `manual_review_required`;
- `request_quality.status`;
- `operation_source`;
- `operation_confidence`;
- `operation_reason`;
- `target_selection_source`;
- `target_selection_confidence`;
- `recall_candidates_count`;
- `returned_candidates_count`;
- `has_context_summary`.

Если `request_quality.status = insufficient`, UI не разрешает select-target и generate. Пользователь должен изменить CR и выполнить analyze заново.

Если `result_summary.status = needs_user_decision`, но `request_quality.status != insufficient`, пользователь может выбрать место изменения вручную.

## Operation, insert scope и target role

Поддерживаемые операции:

- `replace_symbol` — заменить существующий символ;
- `insert_after_symbol` — вставить новый код относительно существующего символа или внутрь класса.

Поддерживаемые `insert_scope`:

- `module_body` — добавление top-level функции или класса в модуль;
- `class_body` — добавление метода внутрь класса;
- пусто — не применимо для `replace_symbol` или еще не определено.

Поддерживаемые роли места изменения:

- `target` — символ будет заменен;
- `anchor` — символ используется как точка вставки;
- `parent_class` — класс, внутрь которого будет добавлен новый метод;
- `unknown` — место изменения не определено.

UI не должен смешивать эти значения. Для `class_body` нужно показывать, что выбранный symbol является родительским классом. Для `module_body` нужно показывать, что выбранный symbol является anchor для вставки после него.

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

UI показывает:

- имя;
- qualname;
- kind;
- file path;
- score/confidence;
- relevance category;
- LLM rank, если есть;
- признак `llm_recommended`;
- признак `ranked_by_llm`;
- reasons;
- docstring;
- requirements.

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

API-вызов `codeui`:

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../select-target \
  -H 'Content-Type: application/json' \
  -d '{
    "selected_qualname": "support_app.storage.ticket_repository.TicketRepository",
    "operation": "insert_after_symbol",
    "insert_scope": "class_body"
  }'
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

Если generate возвращает бизнес-блокировку, UI показывает ее как нормальное состояние, а не как crash.

Пример блокировки:

```json
{
  "pipeline_result": null,
  "result_summary": {
    "status": "needs_user_decision",
    "generation_blocked": true,
    "block_reason": "insufficient_request",
    "message": "Request is insufficient for generation. Rewrite the request and run analyze again.",
    "request_quality_status": "insufficient",
    "missing_information": [
      "конкретное улучшаемое поведение",
      "желаемый результат"
    ],
    "recommended_action": "rewrite_request_and_run_analyze_again"
  }
}
```

Для `block_reason = insufficient_request` UI показывает, что запрос недостаточно конкретен и его нужно переписать.

Для `block_reason = session_not_ready` UI показывает, что сессия не готова к генерации и нужно выбрать target/anchor или выполнить analyze заново.

## Run artifacts и результат запуска

После успешного запуска `codecollector` сохраняет run artifacts в `.runs`.

`codeui` читает их из проекта `codecollector` и строит компактные view-models.

Основные поля result summary:

```json
{
  "status": "ready_for_merge_review",
  "selected_target": "support_app.storage.ticket_repository.TicketRepository",
  "requested_operation": "insert_after_symbol",
  "final_operation": "insert_after_symbol",
  "insert_scope": "class_body",
  "workspace_path": "...",
  "changed_files": [],
  "symbols_in_changed_files": [],
  "verification_passed": true,
  "merge_mode": "dry_run",
  "merge_ready": true,
  "has_generated_test": true,
  "generated_test_files": [],
  "repair_used": false,
  "excluded_files": []
}
```

UI показывает:

- итоговый статус;
- selected target;
- operation;
- insert scope;
- роль места изменения;
- parent class, если добавляется метод внутрь класса;
- expected new symbol kind;
- workspace path;
- changed files;
- symbols in changed files;
- verification status;
- generated test files;
- repair used;
- merge ready;
- excluded files;
- plan summary lines;
- пути run artifacts, trace, request/result внешних вызовов, если они есть.

Если production artifact был исправлен через repair, вкладка “Код” показывает финальный `repair_result.code_artifact`, а primary `generation_result` остается доступен в raw details.

## Import changes

`codegenerator` может вернуть `import_changes` внутри `code_artifact`, а `codecollector` применяет их к target file.

Пример:

```json
{
  "code_artifact": {
    "operation": "insert_after_symbol",
    "target_qualname": "support_app.storage.ticket_repository.TicketRepository",
    "target_file": "support_app/storage/ticket_repository.py",
    "insert_scope": "class_body",
    "expected_new_symbol_kind": "method",
    "parent_qualname": "support_app.storage.ticket_repository.TicketRepository",
    "code": "def export_ticket_ids(self, path: Path) -> None:\n    ...",
    "import_changes": [
      {
        "action": "add_from_import",
        "module": "pathlib",
        "names": ["Path"]
      }
    ]
  }
}
```

UI показывает import changes в составе code artifact и плана применения. В diff они отображаются как обычное изменение файла. Пользователь не выполняет отдельную операцию для imports.

## Проверки

Verification report содержит список blocks.

Пример:

```json
{
  "name": "runtime_py_compile",
  "ok": true,
  "severity": "info",
  "issues": [],
  "details": {}
}
```

UI показывает:

- name;
- ok;
- severity;
- issues;
- details по раскрытию.

Основные блоки:

- `patch_static_semantics`;
- `generated_test_static_semantics`;
- `generated_test_relevance`;
- `runtime_ast_parse`;
- `runtime_py_compile`;
- `runtime_pytest_recommended`.

Если `ok = false`, issues выводятся крупно и понятно. Элементы `issues` могут быть объектами, поэтому их нельзя выводить как строку через `join`. Для issue показываются `code`, `severity`, `message`, `file_path`, `symbol`.

В интерфейсе проверки разделяются на группы:

- production checks — проверки production-кода и обязательных runtime-проверок;
- generated test checks — проверки сгенерированного теста и pytest-падения, относящиеся только к generated test.

Если статус запуска `generated_test_verification_failed`, UI показывает, что production-код можно рассматривать отдельно, а проблема относится к generated test.

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

`generated_test_apply` отображается отдельно. Поддерживаются поля:

- `applied_tests`;
- `count`;
- `skipped`;
- `reason`;
- `message`;
- `verification_failed`;
- `merge_recommended`;
- `excluded_files`;
- `candidate_test_files`.

`skipped=false` означает, что тест применялся в staging workspace для проверки. Это не означает, что тест будет применен в основной проект. Решение о применении определяется через `merge_recommended`, `excluded_files` и `merge_plan`.

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

Пример:

```json
{
  "analysis_usage": {
    "calls": 2,
    "prompt_tokens": 5338,
    "output_tokens": 978,
    "total_tokens": 6316,
    "prompt_chars": 20920,
    "duration_sec": 28.51,
    "timings": {
      "search_plan_total_sec": 6.85,
      "recall_search_sec": 2.75,
      "candidate_rerank_total_sec": 18.74
    }
  }
}
```

Для pipeline/codegenerator UI показывает usage из:

- `external_code_generation.result_summary.llm_usage`;
- `external_test_generation.result_summary.llm_usage`;
- `repair_generation.result_summary.llm_usage`, если есть.

Также UI показывает prompt/context metrics, если они есть в run artifacts:

- request chars;
- target source chars;
- related test chars;
- reference chars;
- full file included;
- trim steps.

## API

Основные группы API:

```text
GET  /api/health
GET  /api/settings
GET  /api/ui-state
PUT  /api/ui-state
POST /api/ui-state/select-project
POST /api/ui-state/requirements-file

GET  /api/projects
POST /api/projects/onboard
POST /api/projects/delete
DELETE /api/projects/{project_id}
POST /api/projects/register

GET  /api/requirements
GET  /api/requirements/tree
GET  /api/requirements/{requirement_id}

GET    /api/change-requests
POST   /api/change-requests
GET    /api/change-requests/{cr_id}
PUT    /api/change-requests/{cr_id}
DELETE /api/change-requests/{cr_id}
GET    /api/change-requests/{cr_id}/runs
POST   /api/change-requests/{cr_id}/analyze
POST   /api/change-requests/{cr_id}/select-target
POST   /api/change-requests/{cr_id}/run
POST   /api/change-requests/{cr_id}/apply-last-run

GET  /api/sessions
GET  /api/sessions/{session_id}

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

### Health и настройки

```bash
curl http://127.0.0.1:8088/api/health
```

```json
{
  "status": "ok",
  "app": "codeui"
}
```

```bash
curl http://127.0.0.1:8088/api/settings
```

### UI-состояние

```bash
curl http://127.0.0.1:8088/api/ui-state
```

```bash
curl -X PUT http://127.0.0.1:8088/api/ui-state \
  -H 'Content-Type: application/json' \
  -d '{
    "selected_project_id": "proj-...",
    "requirements_file_path": "data/requirements.json",
    "selected_requirement_ids": ["REQ-..."],
    "selected_change_request_id": "cr-..."
  }'
```

```bash
curl -X POST http://127.0.0.1:8088/api/ui-state/select-project \
  -H 'Content-Type: application/json' \
  -d '{"project_id": "proj-..."}'
```

```bash
curl -X POST http://127.0.0.1:8088/api/ui-state/requirements-file \
  -H 'Content-Type: application/json' \
  -d '{"path": "/home/stickt/llm/codeui/data/requirements.json"}'
```

### Проекты

```bash
curl http://127.0.0.1:8088/api/projects
```

Подключение проекта выполняется через onboarding в `codecollector`. `input_root` — верхняя папка проекта, внутри которой ожидается `src/` и опционально `ARCHITECT.md` или `ARCHITECTURE.md`. `codeui` не индексирует проект и не читает architecture/knowledge-файлы самостоятельно.

```bash
curl -X POST http://127.0.0.1:8088/api/projects/onboard \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name": "example_project",
    "input_root": "/home/stickt/llm/example_project",
    "full": true,
    "skip_architecture_enrichment": false
  }'
```

Успешный ответ возвращается как `{ "ok": true, "result": ... }`. В UI успешное добавление и успешное удаление показываются одной строкой с раскрываемым компактным описанием без raw JSON. Контролируемая ошибка `codecollector`, например уже подключенный `project_root` или ошибка enrichment, возвращается как `{ "ok": false, ... }` без HTML traceback. Для ошибок UI показывает краткое бизнес-сообщение и раскрываемые технические детали.

Удаление проекта:

```bash
curl -X POST http://127.0.0.1:8088/api/projects/delete \
  -H 'Content-Type: application/json' \
  -d '{"project_id": "proj-..."}'
```

Также доступен endpoint:

```bash
curl -X DELETE http://127.0.0.1:8088/api/projects/proj-...
```

Endpoint `POST /api/projects/register` оставлен как низкоуровневый wrapper старой команды `projects register`, но основной пользовательский сценарий подключения нового проекта в UI использует `/api/projects/onboard`.

### Требования

```bash
curl http://127.0.0.1:8088/api/requirements
```

```bash
curl http://127.0.0.1:8088/api/requirements/tree
```

```bash
curl http://127.0.0.1:8088/api/requirements/LLM-A-000011
```

### Создание CR

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "proj-...",
    "requirement_ids": ["LLM-A-000011"],
    "title": "Изменить текст уведомления",
    "description": "Сделать уведомление на русском языке.",
    "constraints": ["Не менять внешний контракт API"],
    "requested_operation": null,
    "insert_scope": null
  }'
```

### Analyze с автоматическим определением операции

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../analyze \
  -H 'Content-Type: application/json' \
  -d '{}'
```

### Analyze с ручной операцией и областью вставки

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "operation": "insert_after_symbol",
    "insert_scope": "class_body"
  }'
```

### Выбор места изменения

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../select-target \
  -H 'Content-Type: application/json' \
  -d '{
    "selected_qualname": "support_app.storage.ticket_repository.TicketRepository",
    "operation": "insert_after_symbol",
    "insert_scope": "class_body"
  }'
```

### Запуск обработки

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../run
```

### Применение последнего результата

```bash
curl -X POST http://127.0.0.1:8088/api/change-requests/cr-.../apply-last-run
```

### Запуски

```bash
curl http://127.0.0.1:8088/api/runs?limit=50
```

```bash
curl http://127.0.0.1:8088/api/runs?all=true
```

```bash
curl http://127.0.0.1:8088/api/runs/pipeline-.../summary
curl http://127.0.0.1:8088/api/runs/pipeline-.../steps
curl http://127.0.0.1:8088/api/runs/pipeline-.../checks
curl http://127.0.0.1:8088/api/runs/pipeline-.../diff
curl http://127.0.0.1:8088/api/runs/pipeline-.../code
curl http://127.0.0.1:8088/api/runs/pipeline-.../test
curl http://127.0.0.1:8088/api/runs/pipeline-.../raw
```

## Логирование и ошибки

`codeui` логирует:

- запуск приложения;
- чтение конфигурации;
- вызовы CLI `codecollector`;
- рабочую директорию и команду;
- код возврата;
- длительность;
- размер stdout/stderr;
- ошибки чтения/записи JSON;
- изменения UI-состояния;
- создание и изменение CR;
- привязку CR к run;
- чтение run artifacts;
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

Не логируются целиком большие JSON, diff, исходный код, prompt или raw output. Вместо этого логируются размеры, пути и короткие summary. Для операций onboarding/delete проекта логируется краткий статус ответа `codecollector`; подробности controlled errors доступны пользователю в раскрываемых технических деталях.

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

## Проверки разработки

Проверка Python-синтаксиса:

```bash
python -m compileall codeui
```

Проверка JavaScript-синтаксиса:

```bash
node --check codeui/static/app.js
```

## Текущие проблемы и направления дальнейших изменений

Текущие задачи развития UI:

- уточнить отображение unknown-статусов и новых полей codecollector без изменения backend-логики;
- добавить более удобное раскрытие больших verification details;
- добавить отдельное действие очистки CR вместе с техническими артефактами после отдельного подтверждения пользователя;
- улучшить выбор места изменения из полного индекса проекта;
- добавить отдельное представление reference library и используемых reference artifacts;
- расширить поддержку runtime-error workflow, когда пользователь передает traceback или описание ошибки запуска проекта.

## Ограничения текущего состояния

- Аутентификация и авторизация не реализованы.
- Проекты не хранятся в `codeui`; список читается из `codecollector`.
- Требования подключаются как JSON-файл и не редактируются в UI.
- CR хранятся в JSON-файлах.
- Pipeline выполняется в `codecollector`.
- Связь между CR и запусками хранится в JSON-файле CR.
- Общее хранилище состояния — файловое, без отдельной базы данных.
- Основной экран показывает компактные представления run artifacts, не полный `pipeline_run_*.json`.
- Raw JSON доступен только как дополнительный режим просмотра.
- Применение результата выполняется только после отдельного решения пользователя.
- При `insufficient_request` нужно изменить CR и повторить analyze; select-target не считается исправлением недостаточного запроса.
