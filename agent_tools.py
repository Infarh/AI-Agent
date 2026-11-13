import subprocess
from datetime import datetime

COMMAND_TIMEOUT = 120
MAX_OUTPUT_CHARS = 4000


def get_models(client):
    """Возвращает список названий моделей, доступных на сервере Ollama."""
    return [m.model for m in client.list().models]


def get_capabilities(client, model):
    """Возвращает список возможностей модели (thinking, tools и т.д.)."""
    return client.show(model).capabilities or []


def pick_model(models, default_model, choice):
    """Возвращает выбранную модель по номеру из списка.

    При пустом вводе возвращает модель по умолчанию,
    при некорректном номере — None.
    """
    choice = choice.strip()
    if not choice:
        return default_model
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        return models[int(choice) - 1]
    return None


def get_system_time() -> str:
    """Возвращает текущие системные дату и время.

    Returns:
        Дата и время в формате ISO 8601 с часовым поясом.
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _truncate(text):
    """Обрезает длинный текст, оставляя начало и конец, чтобы не перегрузить контекст модели."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text

    head = MAX_OUTPUT_CHARS * 2 // 3
    tail = MAX_OUTPUT_CHARS - head
    omitted = len(text) - MAX_OUTPUT_CHARS
    return f"{text[:head]}\n... [обрезано {omitted} символов] ...\n{text[-tail:]}"


def _run(command, shell=False):
    """Выполняет команду и возвращает её код возврата, вывод и ошибки."""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            timeout=COMMAND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"Команда не завершилась за {COMMAND_TIMEOUT} секунд."

    stdout = _truncate(result.stdout.decode("utf-8", errors="replace").strip())
    stderr = _truncate(result.stderr.decode("utf-8", errors="replace").strip())
    return f"Код возврата: {result.returncode}\nВывод:\n{stdout}\nОшибки:\n{stderr}"


def run_powershell(command: str) -> str:
    """Выполняет произвольную команду PowerShell без ограничений.

    Args:
        command: Команда PowerShell для выполнения.

    Returns:
        Код возврата, стандартный вывод и сообщения об ошибках.
    """
    return _run([
        "powershell",
        "-NoProfile",
        "-Command",
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + command,
    ])


def run_shell(command: str) -> str:
    """Выполняет произвольную shell-команду Linux без ограничений.

    Args:
        command: Shell-команда для выполнения. На пример ls -la или cat file.txt

    Returns:
        Код возврата, стандартный вывод и сообщения об ошибках.
    """
    return _run(command, shell=True)


TOOLS = [get_system_time, run_powershell, run_shell]
