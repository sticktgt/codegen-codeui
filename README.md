# codeui

`codeui` — web-интерфейс и FastAPI-фасад для работы с локальными проектами через `codecollector`.

Приложение помогает пользователю выбрать проект, подключить требования, создать запрос на изменение кода, выполнить анализ, выбрать место изменения, запустить pipeline, посмотреть результат и вручную принять решение о применении workspace к основному проекту.

`codeui` не индексирует код, не строит project context, не генерирует код, не применяет patch самостоятельно и не выполняет проверки проекта. Эти действия выполняет `codecollector`. `codeui` хранит пользовательские CR, вызывает CLI `codecollector`, читает JSON-артефакты запусков и показывает их в компактном виде.

## Роль проекта

`codeui` отвечает за пользовательский workflow:

- выбор и отображение активного проекта;
- добавление проекта через onboarding `codecollector`;
- обновление индекса проекта;
- удаление проекта из `codecollector`;
- подключение JSON-файла требований;
- отображение требований и связанных CR;
- создание и редактирование CR;
- запуск analyze, select target, pipeline и apply;
- отображение результата запуска, шагов, проверок, diff, generated code, generated test, repair и advisory review;
- хранение связи CR с требованиями, сессией и запусками pipeline.

`codeui` не хранит проекты как отдельную бизнес-сущность. Список проектов читается из `codecollector`. В UI-состоянии сохраняется только выбранный проект и выбранные пользовательские элементы интерфейса.

## Основной сценарий

Пользователь открывает UI, выбирает проект, подключает файл требований и выбирает требование. После этого пользователь создает CR, заполняет поля запроса, выполняет анализ и смотрит рекомендации `codecollector`: качество запроса, операцию, область вставки, роль target и кандидатов.

Если запрос достаточно конкретный, пользователь выбирает recommended target или указывает qualname вручную. Затем запускается pipeline. После завершения пользователь просматривает результат, проверки, diff, generated code, generated test, repair, advisory review и merge plan. Применение workspace выполняется отдельным действием пользователя. Применить можно последний результат CR или выбранный запуск на вкладке запусков, если он готов к ручному применению.

## Проекты

В верхней панели отображается активный проект:

- название проекта;
- ID проекта;
- путь к корневой папке проекта.

В выпадающем списке проектов показывается название проекта. При выборе проекта значение сразу сохраняется в UI-состоянии.

### Добавление проекта

Кнопка `Добавить проект` вызывает onboarding в `codecollector`:

```bash
python -m codecollector projects onboard \
  --input-root /path/to/project_root \
  --project-name example_project \
  --full
```

`input_root` — верхняя папка подключаемого проекта. Внутри нее ожидается папка `src/`. Файл `ARCHITECT.md` или `ARCHITECTURE.md` может присутствовать рядом с `src/`. Если архитектурный файл найден, enrichment выполняет `codecollector`. Если файла нет, проект подключается без enrichment.

В UI форма добавления содержит:

- название проекта;
- путь к папке проекта;
- флаг полного rebuild индекса;
- флаг пропуска LLM enrichment архитектуры.

После успешного добавления проект выбирается активным. Результат показывается одной свернутой строкой `Проект подключен`. В раскрытии показывается краткая информация: ID, путь, число файлов, модулей, символов, статус knowledge enrichment, warnings и unmatched mentions, если они есть.

Если `codecollector` возвращает controlled failure, UI показывает краткое сообщение и раскрываемые детали. Для duplicate root показывается, что проект с таким путем уже подключен, а также existing project id, existing project name и project root.

### Обновление индекса

Кнопка `Обновить индекс` вызывает:

```bash
python -m codecollector projects reindex \
  --project-id <project_id> \
  --full
```

Кнопка доступна только для выбранного проекта. Результат показывается одной свернутой строкой `Индекс обновлен`. В раскрытии показываются ID, путь, full rebuild, количество проиндексированных файлов, модулей, символов, search documents, embedded documents и режим vector sync.

### Удаление проекта

Кнопка `Удалить проект` вызывает удаление выбранного проекта после подтверждения пользователя:

```bash
python -m codecollector projects delete --project-id <project_id>
```

После удаления список проектов обновляется. Если удаленный проект был активным, активный проект сбрасывается. Результат показывается одной свернутой строкой `Проект удален`. В раскрытии показывается cleanup summary и warnings, если они есть.

## Требования

`codeui` читает требования из JSON-файла. Поддерживаются два формата верхнего уровня:

```json
{
  "requirements": []
}
```

и

```json
[]
```

Требования отображаются иерархически по `parent_id`. Если `parent_id` пустой или `null`, требование считается корневым. Если у требования нет отдельного заголовка, в списке используется начало `description`.

Основные поля требования:

- `id`;
- `project_id`;
- `type`;
- `status`;
- `priority`;
- `description`;
- `note`;
- `author`;
- `version`;
- `parent_id`;
- `verification_status`;
- `created_at`;
- `acceptance_criteria`;
- `tags`;
- `user_roles`;
- `trace_span`, `trace_start_char`, `trace_end_char`.

Требования в UI не редактируются. При создании CR в него сохраняется snapshot выбранных требований. Это позволяет отображать CR даже в случае недоступности исходного файла требований.

Если выбранное требование связано с CR, UI показывает связанные запросы. При выбранном активном проекте основным списком показываются только CR этого проекта. CR других проектов показываются отдельно в свернутом блоке с предупреждением.

## CR

CR — пользовательский запрос на изменение кода. CR создается и хранится в `codeui` в виде JSON-файла.

CR содержит:

- технический `cr_id`;
- короткий пользовательский код вида `CR-000001`;
- `project_id` активного проекта `codecollector`;
- связанные `requirement_ids`;
- snapshot требований;
- title, description, constraints и notes;
- requested operation и insert scope;
- статус;
- session id;
- recommended target и selected target;
- связанные run ids;
- последний run id и workspace id;
- служебные raw-данные analyze, select target, run и apply.

CR можно редактировать до применения результата. При изменении исходных полей CR результаты анализа и последнего запуска сбрасываются, потому что они уже не соответствуют новому содержанию запроса.

Финальный статус CR — `applied`. В этом статусе CR нельзя редактировать, удалять, анализировать, запускать повторно или применять повторно.

Список CR фильтруется по активному проекту `codecollector`. Если проект не выбран, показываются все CR.

## Analyze

Analyze вызывает команду `codecollector sessions analyze`. Операция может быть выбрана пользователем заранее или определена `codecollector` автоматически.

UI показывает:

- статус анализа;
- качество запроса;
- missing information;
- requested operation;
- insert scope;
- operation source;
- operation confidence;
- operation reason;
- recommended target;
- target role;
- target confidence;
- target reason;
- manual review required;
- candidates;
- warnings;
- usage и timings.

`request_quality.status` обрабатывается так:

- `processable` — запрос можно запускать при наличии выбранного или рекомендованного target;
- `uncertain` — UI показывает предупреждение, но позволяет продолжить после решения пользователя;
- `insufficient` — generate блокируется, пользователь должен изменить CR и выполнить analyze заново.

Если `codecollector` возвращает `generation_blocked=true`, UI показывает это как бизнес-состояние, а не как техническую ошибку.

## Operation, target role и insert scope

UI различает объект замены и точку вставки.

Для `replace_symbol` выбранный target является изменяемым symbol. Его роль обычно `target`.

Для `insert_after_symbol` выбранный symbol может быть:

- `anchor` — точка вставки;
- `parent_class` — класс, внутрь которого добавляется новый метод.

Поддерживаемые `insert_scope`:

- `module_body` — новый top-level symbol вставляется в тело модуля;
- `class_body` — новый метод вставляется в тело класса.

UI показывает requested operation, final operation, insert scope, expected new symbol kind, parent qualname, selected target, target role, confidence и reason.

## Запуск pipeline

Pipeline запускается через `codecollector sessions generate`. `codecollector` собирает context pack, вызывает `codegenerator`, применяет artifact в staging workspace, выполняет проверки, при необходимости запускает repair, генерирует test artifact и формирует merge plan.

`codeui` не выполняет эти шаги самостоятельно. Он запускает CLI-команду, сохраняет связь CR с run id и читает run artifacts из `.runs` проекта `codecollector`.

Список запусков фильтруется по активному проекту через связанные CR. Запуски, созданные вне `codeui` и не связанные с CR, не участвуют в проектной фильтрации.

На вкладке `3. Запуски` можно открыть конкретный запуск. Если запуск готов к ручному применению и содержит workspace id, в панели `Результат запуска` доступна кнопка `Применить`. Она применяет workspace именно выбранного запуска, а не обязательно последнего запуска CR. Если запуск связан с CR, после успешного применения CR получает финальный статус `applied`, а `applied_run_id` указывает на выбранный запуск.

## Результат запуска

На вкладке `Результат` показываются:

- итоговый статус;
- selected target;
- target role;
- requested operation;
- final operation;
- insert scope;
- workspace id;
- workspace path;
- changed files;
- symbols in changed files;
- verification status;
- repair used;
- generated test status;
- generated test files;
- excluded files;
- merge ready;
- merge mode;
- Review verdict, если выполнен advisory review;
- usage по generation, repair, test generation и generated test review.

Если статус равен `generated_test_verification_failed`, UI показывает, что production artifact был применен в staging и прошел базовые проверки, но generated test не прошел verification. Generated test может быть исключен из apply/merge. Такой запуск не отображается как полностью успешный автоматический результат; он предназначен для ручного review.

## Шаги pipeline

На вкладке `Шаги` показывается timeline из `pipeline_result.steps`:

- step name;
- status;
- duration;
- tokens, если usage доступен;
- summary;
- error type;
- error message;
- exception class.

Шаг `generated_test_failure_review` отображается как обычный pipeline step и помечается как `advisory review`. Если в данных есть шаг `verification`, review-step показывается после него.

Для LLM-шагов usage подтягивается из связанных блоков результата:

- для `generated_test_failure_review` используется `generated_test_review.llm_usage` или `generated_test_failure_review.llm_usage`;
- для `external_repair_after_patch_static_semantics` используется `repair_generation.result_summary.llm_usage`.

Проверочные шаги после repair не наследуют usage repair generation.

## Review

Если `codecollector` передал результат advisory review generated test failure, в запуске появляется вкладка `Review`. При наличии review эта вкладка открывается первой. Если review нет, первой открывается вкладка `Результат`.

UI поддерживает результат review из полей run JSON и artifact-файлов:

- `generated_test_review`;
- `generated_test_failure_review`;
- `pipeline_result.generated_test_review`;
- `pipeline_result.generated_test_failure_review`;
- `generated_test_review_result.json`;
- `generated_test_failure_review_result.json`.

Review отображается как advisory-информация. Он не перезаписывает итоговый статус pipeline и не скрывает verification warnings.

Во вкладке показываются:

- verdict;
- confidence;
- production code quality;
- generated test quality;
- should keep production code;
- recommended action;
- reasons;
- production risks;
- test issues;
- trace path;
- usage;
- raw review details.

## Проверки и warnings

На вкладке `Проверки` показывается `verification_report`.

Проверки группируются как production checks и generated test checks. Для каждого блока показываются name, ok, severity, issues и details. Issues выводятся как структурированные объекты с code, severity, message, file path, symbol и details.

`possible_existing_method_contract_lost` отображается как advisory warning. UI показывает method, message и missing exception contracts. Такое предупреждение не считается hard failure само по себе и не скрывается даже при положительном advisory review.

## Generated test

Если generated test создан, UI показывает:

- test artifact source;
- generated test files;
- candidate test files;
- generated test apply status;
- reason, message, error type и trace path при ошибке;
- excluded files.

`excluded_files` показываются с тем же casing, который пришел в JSON. Пути не нормализуются к lowercase.

Если generated test не прошел verification, UI показывает, что generated test исключен из apply/merge, если это отражено в `generated_test_apply` или `merge_plan`.

## Repair

Если repair использовался, UI показывает:

- `repair_used`;
- repair generation summary;
- repair trace path;
- repair usage;
- repair status;
- error type и message, если они есть.

Если repair вернул финальный `code_artifact`, вкладка `Код` показывает именно artifact после repair. Primary generation result остается доступен в raw/details.

## Diff и merge plan

На вкладке `Diff` показываются:

- changed files из workspace;
- files, рекомендованные к merge;
- generated test files;
- excluded files;
- unified diff.

Эти списки не смешиваются. Workspace может содержать generated test, который использовался для verification, но исключен из merge.

Merge plan показывает:

- mode;
- ready for manual merge review;
- workspace id;
- workspace path;
- changed files;
- symbols in changed files;
- linked requirements;
- recommended tests;
- recommended test commands;
- excluded files;
- summary lines.

Если recommended tests относятся к generated test, который excluded, UI показывает предупреждение рядом с recommended tests.

## Код и import changes

Вкладка `Код` показывает production code artifact. Для artifact отображаются operation, target qualname, target file, insert scope, parent qualname, generated code и import changes.

Если `external_code_generation.result_summary.code_artifact_summary.import_changes_count` передан в run result, UI показывает это значение в summary artifact.

Import changes применяются `codecollector` и видны в unified diff как обычные изменения файла.

## API

Основные endpoints:

```text
GET  /api/health
GET  /api/settings
GET  /api/ui-state
PUT  /api/ui-state
POST /api/ui-state/select-project
POST /api/ui-state/requirements-file

GET  /api/projects
POST /api/projects/onboard
POST /api/projects/reindex
POST /api/projects/delete
DELETE /api/projects/{project_id}

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

## Конфигурация

Основной файл настроек — `config.yaml`.

В нем задаются:

- параметры приложения и HTTP-сервера;
- уровень логирования;
- путь к `codecollector`;
- Python-команда и module name для CLI-вызовов;
- timeout CLI-команд;
- пути к `.runs`, `.state` и `.workspaces` внутри `codecollector`;
- путь хранения CR;
- источник требований;
- UI state file;
- trace-директория CLI-вызовов.

`data/ui_state.json` хранит выбранный проект, путь к файлу требований, выбранные требования и выбранный CR.

## Trace CLI-вызовов

`codeui` логирует каждый вызов CLI `codecollector`: command, cwd, duration, returncode, размер stdout и stderr.

Если включен `command_trace`, stdout и stderr вызовов сохраняются в директорию `.trace/codecollector_cli`.

Для одного вызова создаются файлы:

```text
<timestamp>_<command-label>_<hash>.stdout.txt
<timestamp>_<command-label>_<hash>.stderr.txt
```

Команда `projects list` не сохраняется в trace, потому что используется часто для обновления списка проектов и обычно не нужна для диагностики.

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
    main.py
    config.py
    dependencies.py
    errors.py
    logger.py
    api/
    schemas/
    services/
    static/
  tests/
```

Основные сервисы:

- `codeui/services/codecollector_client.py` вызывает CLI `codecollector`;
- `codeui/services/command_runner.py` запускает команды и сохраняет trace;
- `codeui/services/change_request_service.py` хранит CR;
- `codeui/services/requirements_service.py` читает требования;
- `codeui/services/run_artifact_service.py` читает run artifacts;
- `codeui/services/run_view_service.py` строит compact view для UI;
- `codeui/services/ui_state_service.py` хранит состояние UI.

Основные frontend-файлы:

- `codeui/static/index.html`;
- `codeui/static/app.js`;
- `codeui/static/styles.css`.

## Запуск

```bash
cd /home/stickt/llm/codeui
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m codeui
```

По умолчанию UI доступен по адресу:

```text
http://127.0.0.1:8088/
```

## Проверки

```bash
python -m compileall -q codeui
node --check codeui/static/app.js
python -m pytest -q
```

## Ограничения

В приложении нет аутентификации и авторизации. Хранилище CR и UI-состояния файловое. Требования читаются из JSON-файла и не редактируются в UI. Pipeline полностью выполняется в `codecollector`. Применение workspace выполняется только после отдельного действия пользователя.
