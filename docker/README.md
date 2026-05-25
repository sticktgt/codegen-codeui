# Docker-запуск codeui + codecollector + codegenerator

Docker-упаковка запускает внешний интерфейс через `codeui`. Внутри app-контейнера проекты лежат соседними каталогами:

```text
/home/stickt/llm/codecollector
/home/stickt/llm/codegenerator
/home/stickt/llm/codeui
```

Это сохраняет текущую схему взаимодействия: `codeui` вызывает `codecollector` через CLI, а `codecollector` вызывает `codegenerator` через CLI.

## Сервисы

- `codeui-app` — Python-контейнер с тремя проектами. Наружу открыт web/API `codeui` на порту `8088`.
- `pgvector` — PostgreSQL + pgvector для graph/vector storage `codecollector`.
- `ollama` — локальный Ollama для embeddings `nomic-embed-text-v2-moe`.
- `ollama-pull-embedding` — одноразовый setup-сервис для загрузки embedding-модели.

Генерация и analyze продолжают использовать облачный Ollama endpoint из config.yaml: `https://ollama.com`.

## Внешние каталоги

Все изменяемые данные вынесены в `./runtime`:

```text
runtime/
  codeui/
    data/
      change_requests/
      ui_state.json
    trace/
  codecollector/
    runs/
    state/
    workspaces/
  codegenerator/
    runs/
  requirements/
  projects/
```

Назначение каталогов:

- `runtime/codeui/data/change_requests` — JSON-файлы CR.
- `runtime/codeui/data/ui_state.json` — выбранный проект, выбранный файл требований и другое UI-состояние.
- `runtime/codeui/trace` — traces CLI-вызовов `codecollector`.
- `runtime/codecollector/runs` — run artifacts pipeline; эту папку читает `codeui`.
- `runtime/codecollector/state` — libraries, projects, sessions `codecollector`.
- `runtime/codecollector/workspaces` — staging workspaces `codecollector`.
- `runtime/codegenerator/runs` — traces/runs `codegenerator`.
- `runtime/requirements` — доступная из UI папка для JSON-файлов требований.
- `runtime/projects` — доступная из UI папка для подключаемых проектов.

В UI путь к файлу требований нужно указывать как путь внутри контейнера, например:

```text
/runtime/requirements/requirements.json
```

Проекты для onboarding или регистрации лучше размещать под:

```text
/projects
```

Например:

```text
/projects/example_project
```

## Первый запуск

Из каталога, где лежат `codecollector`, `codegenerator`, `codeui`, `Dockerfile` и `docker-compose.yml`:

```bash
mkdir -p \
  runtime/codeui/data/change_requests \
  runtime/codeui/trace \
  runtime/codecollector/runs \
  runtime/codecollector/state \
  runtime/codecollector/workspaces \
  runtime/codegenerator/runs \
  runtime/requirements \
  runtime/projects

docker compose up -d pgvector ollama
```

Загрузить embedding-модель:

```bash
docker compose --profile setup run --rm ollama-pull-embedding
```

Собрать и запустить приложение:

```bash
docker compose up -d --build codeui-app
```

Открыть UI:

```text
http://localhost:8088
```

## Пересборка app-контейнера

Если менялся код одного из трех проектов:

```bash
docker compose up -d --build codeui-app
```

`pgvector` и `ollama` при этом не пересобираются и сохраняют свои данные в named volumes.

## Остановка

Остановить сервисы без удаления данных:

```bash
docker compose down
```

Удалять named volumes нужно только если требуется полностью сбросить PostgreSQL/pgvector или локальные модели Ollama:

```bash
docker compose down -v
```
