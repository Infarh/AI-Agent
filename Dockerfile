FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py agent_tools.py .

# непривилегированный пользователь: команды агента не выполняются от root
RUN useradd --create-home --shell /bin/bash agent
USER agent

# host.docker.internal — Ollama на хосте (Docker Desktop),
# http://ollama:11434 — Ollama в контейнере в сети ollama-network (см. run.cmd)
CMD ["python", "/app/app.py", "http://ollama:11434"]
