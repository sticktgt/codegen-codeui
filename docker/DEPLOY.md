# Docker-развертывание codeui/codecollector/codegenerator

Документ описывает запуск Docker-версии приложения рядом с локальным Python-запуском и перенос готового app-образа на другую машину.

## Назначение compose-файла

`docker-compose.yml` не собирает app-образ. Он только запускает уже существующий образ:

```bash
docker build -t codeui-suite:latest .
docker compose up -d
```

Так один и тот же compose-файл можно использовать и на машине разработки, и на другой машине после `docker load`.

## Порты

Docker-версия использует отдельные host-порты:

- `18088 -> 8088` для web/API `codeui`;
- `15432 -> 5432` для docker-экземпляра `pgvector`;
- `11435 -> 11434` для docker-экземпляра `ollama`.

Внутри Docker-сети сервисы остаются доступны по обычным адресам:

- `pgvector:5432`;
- `ollama:11434`.

## Данные

Runtime-папка остается `./runtime` рядом с compose-файлом:

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

Создание папок:

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
```

В UI путь к требованиям указывается как контейнерный путь, например:

```text
/runtime/requirements/requirements.json
```

Путь к проекту указывается как контейнерный путь, например:

```text
/projects/example_project
```

## pgvector

Для Docker-версии используется отдельный volume:

```text
codeui_pgvector_data
```

Он не пересекается с локальным `pgvector_data`, который может использоваться локальным Python-запуском.

## Ollama

Docker-версия использует сервис `ollama` и volume `ollama_data` из compose-проекта. Если embedding-модель еще не скачана, выполнить:

```bash
docker compose --profile setup run --rm ollama-pull-embedding
```

## Локальный запуск Docker-версии

На машине разработки:

```bash
cd /home/stickt/llm

docker build -t codeui-suite:latest .
docker compose up -d pgvector ollama
docker compose --profile setup run --rm ollama-pull-embedding
docker compose up -d codeui-app
```

Открыть:

```text
http://localhost:18088/
```

## Обновление после изменения кода на машине разработки

```bash
cd /home/stickt/llm

docker build -t codeui-suite:latest .
docker compose up -d --no-deps --force-recreate codeui-app
```

`pgvector`, `ollama`, их volumes и `runtime` при этом не пересоздаются.

## Перенос на другую машину

На машине разработки:

```bash
cd /home/stickt/llm

docker build -t codeui-suite:latest .
docker save codeui-suite:latest | gzip > codeui-suite-latest.tar.gz
```

На целевую машину перенести:

```text
codeui-suite-latest.tar.gz
docker-compose.yml
```

На целевой машине:

```bash
mkdir -p /opt/codeui-suite
cd /opt/codeui-suite

gzip -dc codeui-suite-latest.tar.gz | docker load

mkdir -p \
  runtime/codeui/data/change_requests \
  runtime/codeui/trace \
  runtime/codecollector/runs \
  runtime/codecollector/state \
  runtime/codecollector/workspaces \
  runtime/codegenerator/runs \
  runtime/requirements \
  runtime/projects
```

Скопировать требования и проект:

```bash
cp /path/to/requirements.json runtime/requirements/requirements.json
cp -a /path/to/project runtime/projects/project
```

Запустить:

```bash
docker compose up -d pgvector ollama
docker compose --profile setup run --rm ollama-pull-embedding
docker compose up -d codeui-app
```

Открыть:

```text
http://<server-host>:18088/
```

## Обновление app-образа на другой машине

На машине разработки собрать и экспортировать новый образ:

```bash
cd /home/stickt/llm

docker build -t codeui-suite:latest .
docker save codeui-suite:latest | gzip > codeui-suite-latest.tar.gz
```

На целевой машине заменить архив и выполнить:

```bash
cd /opt/codeui-suite

gzip -dc codeui-suite-latest.tar.gz | docker load
docker compose up -d --no-deps --force-recreate codeui-app
```

`pgvector`, `ollama`, `runtime` и volumes не удаляются и не пересоздаются.
