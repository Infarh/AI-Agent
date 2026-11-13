@echo off
rem Запуск агента в контейнере: каталог ./data монтируется в /app/data,
rem рабочий каталог агента — /app/data, поэтому он видит реальные файлы.
rem Контейнер подключается к сети ollama-network, где Ollama доступна как http://ollama:11434.
if not exist "%~dp0data" mkdir "%~dp0data"
docker run -it --rm ^
  --network ollama-network ^
  -v "%~dp0data:/app/data" ^
  -w /app/data ^
  ai-agent-sandbox ^
  python /app/app.py http://ollama:11434
