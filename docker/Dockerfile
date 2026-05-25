FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/home/stickt/llm/codecollector:/home/stickt/llm/codegenerator:/home/stickt/llm/codeui

WORKDIR /home/stickt/llm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY docker/requirements-app.txt /tmp/requirements-app.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements-app.txt

COPY codecollector/ /home/stickt/llm/codecollector/
COPY codegenerator/ /home/stickt/llm/codegenerator/
COPY codeui/ /home/stickt/llm/codeui/

# Docker-конфиги накладываются поверх локальных config.yaml только внутри образа.
COPY docker/config.codecollector.yaml /home/stickt/llm/codecollector/config.yaml
COPY docker/config.codeui.yaml /home/stickt/llm/codeui/config.yaml

RUN mkdir -p \
      /home/stickt/llm/codeui/data/change_requests \
      /home/stickt/llm/codeui/.trace/codecollector_cli \
      /home/stickt/llm/codecollector/.runs \
      /home/stickt/llm/codecollector/.state \
      /home/stickt/llm/codecollector/.workspaces \
      /home/stickt/llm/codegenerator/runs \
      /runtime/requirements \
      /projects

WORKDIR /home/stickt/llm/codeui
EXPOSE 8088

CMD ["python", "-m", "codeui"]
