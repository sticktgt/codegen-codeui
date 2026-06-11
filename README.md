# codeui

`codeui` — веб-интерфейс и FastAPI-фасад для работы с локальными проектами через `codecollector`.

Приложение помогает выбрать проект, подключить требования, создать запрос на изменение кода, выполнить анализ, выбрать место изменения, запустить цепочку выполнения, просмотреть результат, применить workspace и посмотреть связи требований со структурой проекта.

`codeui` не индексирует код, не собирает context pack, не генерирует код, не применяет patch самостоятельно и не выполняет проверки проекта. Эти действия выполняет `codecollector`. `codeui` хранит CR, вызывает CLI `codecollector`, читает JSON-артефакты запусков и показывает их в интерфейсе.

## Назначение

`codeui` поддерживает пользовательский workflow:

1. Выбрать активный проект.
2. Подключить JSON-файл требований.
3. Выбрать требование.
4. Создать CR.
5. Выполнить analyze.
6. Выбрать recommended target или указать target вручную.
7. Запустить pipeline.
8. Просмотреть результат, шаги, проверки, diff, generated code, generated test, repair и review.
9. Применить workspace после ручного решения пользователя.
10. Посмотреть карту проекта и схему проекта с привязкой требований к модулям и символам.

## Основные возможности

- Отображение проектов из `codecollector`.
- Выбор активного проекта.
- Подключение проекта через onboarding `codecollector`.
- Переиндексация проекта.
- Удаление проекта из `codecollector`.
- Подключение JSON-файла требований.
- Отображение дерева требований.
- Создание и редактирование CR.
- Связь CR с требованиями.
- Analyze CR.
- Выбор recommended или manual target.
- Запуск pipeline.
- Отображение результата запуска, шагов, проверок, diff, code artifact, test artifact, repair и advisory review.
- Применение последнего workspace.
- Передача внешнего кода CR и requirement ids в `workspaces apply` для traceability.
- Отображение карты проекта по `knowledge.yaml` и `requirements.json`.
- Отображение схемы проекта с требованиями, связанными с модулями и символами.
- Сохранение UI state.
- Сохранение trace CLI-вызовов.

## Вкладки интерфейса

### 1. Требования

Вкладка показывает дерево требований из подключённого JSON-файла. Требования можно выбрать для создания CR. Если требование связано с CR, справа показываются связанные запросы.

### 2. Запросы

Вкладка показывает CR активного проекта. CR можно создать, отредактировать, проанализировать, выбрать target, запустить и применить последний workspace.

### 3. Запуски

Вкладка показывает run artifacts. Для запуска доступны summary, steps, checks, diff, code, test, review и raw data.

### Карта проекта

Вкладка строит графическую карту связей требований со структурой проекта. Данные берутся из `requirements.json` и `.codecollector/knowledge.yaml` выбранного проекта.

На карте:

- слева отображаются требования;
- справа отображается иерархическая структура проекта;
- связи требований с модулями и символами показаны линиями;
- клик по требованию подсвечивает его связи;
- клик по элементу проекта подсвечивает требования, связанные с этим элементом;
- клик по коду требования переводит на вкладку `1. Требования` и выбирает требование;
- CR не отображаются.

### Схема проекта

Вкладка показывает структуру проекта и список требований со связанными элементами.

Слева отображается дерево проекта. Справа отображаются требования и элементы проекта, связанные с ними. Бейдж требования в дереве кликабелен и переводит на вкладку `1. Требования`.

Ширину панели структуры проекта можно изменить разделителем. Выбранная ширина сохраняется в `localStorage`.

## Проекты

В верхней панели отображается активный проект:

- название проекта;
- project id;
- путь к корневой папке проекта.

Список проектов читается из `codecollector`. В UI state сохраняется выбранный проект.

### Подключение проекта

Кнопка `Добавить проект` вызывает:

```bash
python -m codecollector projects onboard \
  --input-root /path/to/project_root \
  --project-name example_project \
  --full
```

Внутри `input_root` ожидается папка `src/`. Архитектурный файл `ARCHITECT.md` или `ARCHITECTURE.md` может находиться рядом с `src/`.

Форма подключения содержит:

- название проекта;
- путь к папке проекта;
- флаг полного rebuild индекса;
- флаг пропуска LLM enrichment архитектуры.

После успешного подключения проект выбирается активным.

### Переиндексация

Кнопка `Обновить индекс` вызывает:

```bash
python -m codecollector projects reindex \
  --project-id <project_id> \
  --full
```

Результат переиндексации показывается в раскрываемом блоке.

### Удаление проекта

Кнопка `Удалить проект` вызывает:

```bash
python -m codecollector projects delete --project-id <project_id>
```

Удаление выполняется после подтверждения пользователя. После удаления список проектов обновляется.

## Требования

`codeui` читает требования из JSON-файла. Поддерживаются форматы:

```json
{
  "requirements": []
}
```

и

```json
[]
```

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

Требования в UI не редактируются. При создании CR в него сохраняется snapshot выбранных требований.

## CR

CR — пользовательский запрос на изменение кода. CR хранится в `codeui` как JSON-файл.

CR содержит:

- технический `cr_id`;
- внешний код CR;
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
- raw-данные analyze, select target, run и apply.

CR можно редактировать до применения результата. При изменении исходных полей CR результаты анализа и последнего запуска сбрасываются.

Финальный статус CR — `applied`. В этом статусе CR нельзя редактировать, удалять, анализировать, запускать повторно или применять повторно.

## Analyze

Analyze вызывает:

```bash
python -m codecollector sessions analyze
```

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

- `processable` — запуск разрешён при наличии target;
- `uncertain` — показывается предупреждение, пользователь может продолжить;
- `insufficient` — generate блокируется до уточнения CR.

## Operation, target role и insert scope

UI различает объект замены и точку вставки.

Для `replace_symbol` выбранный target является изменяемым symbol.

Для `insert_after_symbol` выбранный symbol может быть:

- `anchor` — точка вставки;
- `parent_class` — класс, внутрь которого добавляется новый метод.

Поддерживаемые `insert_scope`:

- `module_body` — top-level вставка в модуль;
- `class_body` — вставка метода в класс.

UI показывает requested operation, final operation, insert scope, expected new symbol kind, parent qualname, selected target, target role, confidence и reason.

## Запуск pipeline

Pipeline запускается через:

```bash
python -m codecollector sessions generate
```

`codecollector` выполняет цепочку:

1. Обновление индекса.
2. Подбор или подтверждение target.
3. Сбор context pack.
4. Подбор reference artifacts.
5. Вызов `codegenerator generate`.
6. Статическую проверку code artifact.
7. Применение artifact в staging workspace.
8. Статическую проверку patch.
9. Repair при блокирующих ошибках производственного кода.
10. Генерацию generated test.
11. Проверку generated test.
12. Runtime-проверки проекта.
13. Advisory review generated test failure при необходимости.
14. Формирование merge plan.

`codeui` запускает CLI-команду, сохраняет связь CR с run id и читает artifacts из `.runs` проекта `codecollector`.

## Результат запуска

На вкладке run result показываются:

- итоговый статус;
- selected target;
- target role;
- requested operation;
- final operation;
- insert scope;
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
- advisory review verdict;
- usage по generation, repair, test generation и generated test review.

## Шаги pipeline

Вкладка steps показывает timeline из run JSON:

- step name;
- status;
- duration;
- tokens, если usage доступен;
- summary;
- error type;
- error message;
- exception class.

Ошибки показываются прямо в строке шага. Длинные сообщения раскрываются отдельным блоком.

## Checks, generated test, repair и review

Вкладка checks показывает `verification_report`. Проверки группируются как production checks и generated test checks.

Generated test отображается отдельно: test artifact, файлы, apply status, excluded files и ошибки.

Repair отображается отдельно: repair status, trace path, usage, error type, message и итоговый artifact.

Advisory review отображается как рекомендательная информация. Он не заменяет итоговый статус pipeline.

## Diff и код

Вкладка diff показывает:

- changed files из workspace;
- files, рекомендованные к merge;
- generated test files;
- excluded files;
- unified diff.

Вкладка code показывает production code artifact после repair, если repair использовался. Primary generation остается доступен в raw/details.

## Apply workspace

Применение последнего результата CR вызывает:

```bash
python -m codecollector workspaces apply \
  --workspace-id <workspace_id> \
  --change-request-id <external_cr_code> \
  --requirement-id <requirement_id>
```

В `--change-request-id` передаётся внешний код CR, а не внутренний `cr_id`. Requirements передаются как `--requirement-id` для записи traceability в `knowledge.yaml`.

После успешного apply CR получает статус `applied`.

## Project schema API

Для вкладок `Карта проекта` и `Схема проекта` используется endpoint:

```text
GET /api/project-schema
```

Endpoint читает:

- `<project_root>/.codecollector/knowledge.yaml`;
- текущий `requirements.json` из UI state.

Сервис `ProjectSchemaService` строит модель из двух файлов и может использоваться отдельно от формы UI:

```python
ProjectSchemaService().build_from_files(
    knowledge_path=knowledge_path,
    requirements_path=requirements_path,
)
```

Модель содержит:

- requirements;
- project nodes;
- links requirement → module/symbol;
- counters;
- путь к `knowledge.yaml`.

Тестовые modules и symbols скрываются из карты и схемы проекта.

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

GET  /api/project-schema

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

В конфигурации задаются:

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

Если включен `command_trace`, stdout и stderr вызовов сохраняются в `.trace/codecollector_cli`.

Для одного вызова создаются файлы:

```text
<timestamp>_<command-label>_<hash>.stdout.txt
<timestamp>_<command-label>_<hash>.stderr.txt
```

Команда `projects list` не сохраняется в trace, потому что используется часто для обновления списка проектов.

## Структура проекта

```text
codeui/
  README.md
  config.yaml
  pyproject.toml
  data/
    requirements.json
    ui_state.json
    change_requests/
  codeui/
    api/
    schemas/
    services/
    static/
    main.py
    config.py
    dependencies.py
  tests/
  docker/
```

Основные backend-элементы:

- `codeui/main.py` — FastAPI-приложение;
- `codeui/dependencies.py` — зависимости сервисов;
- `codeui/api/` — HTTP routes;
- `codeui/schemas/` — Pydantic-схемы;
- `codeui/services/codecollector_client.py` — вызов CLI `codecollector`;
- `codeui/services/command_runner.py` — запуск команд и trace;
- `codeui/services/change_request_service.py` — хранение CR;
- `codeui/services/requirements_service.py` — чтение требований;
- `codeui/services/run_artifact_service.py` — чтение run artifacts;
- `codeui/services/run_view_service.py` — compact view запусков;
- `codeui/services/project_schema_service.py` — модель карты и схемы проекта;
- `codeui/services/ui_state_service.py` — состояние UI.

Основные frontend-элементы:

- `codeui/static/index.html` — HTML-разметка;
- `codeui/static/app.js` — основной UI;
- `codeui/static/project_schema_view.js` — карта проекта и схема проекта;
- `codeui/static/styles.css` — стили.

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
node --check codeui/static/project_schema_view.js
python -m pytest -q
```

## Ограничения и недоработки

- В приложении нет аутентификации и авторизации.
- Хранилище CR и UI state файловое.
- Требования читаются из JSON-файла и не редактируются в UI.
- Pipeline полностью выполняется в `codecollector`.
- Применение workspace выполняется только после отдельного действия пользователя.
- Карта проекта и схема проекта отображают только связи из `knowledge.yaml` и `requirements.json`.
- CR на карте проекта и схеме проекта не отображаются.
- Переход на часть кода из карты проекта не реализован.
- Карта проекта является статическим SVG-представлением без drag/zoom/pan.
