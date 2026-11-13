import os
import re
import shutil
import stat
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import pwd
except ImportError:  # Windows
    pwd = None

COMMAND_TIMEOUT = 120
MAX_OUTPUT_CHARS = 4000
MAX_LIST_ENTRIES = 200
MAX_SEARCH_MATCHES = 100


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


def _owner(st):
    """Возвращает имя владельца файла по данным stat."""
    if pwd is None:
        return "н/д"
    try:
        return pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        return str(st.st_uid)


def get_cwd() -> str:
    """Возвращает текущий рабочий каталог агента.

    Returns:
        Абсолютный путь текущего каталога.
    """
    return f"Текущий каталог: {Path.cwd()}"


def change_directory(path: str) -> str:
    """Меняет текущий рабочий каталог агента.

    Args:
        path: Путь к каталогу, абсолютный или относительный.

    Returns:
        Новый текущий каталог или сообщение об ошибке.
    """
    try:
        os.chdir(Path(path).expanduser())
    except OSError as error:
        return f"Не удалось перейти в каталог {path}: {error}"
    return f"Текущий каталог: {Path.cwd()}"


def list_files(path: str = ".") -> str:
    """Выводит список файлов и подкаталогов по указанному пути.

    Args:
        path: Каталог для просмотра, по умолчанию текущий.

    Returns:
        Имена файлов с размерами и подкаталоги с завершающим слэшем.
    """
    directory = Path(path).expanduser()
    if not directory.is_dir():
        return f"Не каталог: {path}"

    try:
        entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError as error:
        return f"Не удалось прочитать каталог {path}: {error}"

    lines = []
    for entry in entries[:MAX_LIST_ENTRIES]:
        if entry.is_dir():
            lines.append(f"{entry.name}/")
        else:
            lines.append(f"{entry.name}\t{entry.stat().st_size} Б")

    result = f"Каталог {directory} ({len(entries)} элементов):\n" + "\n".join(lines)
    if len(entries) > MAX_LIST_ENTRIES:
        result += f"\n... показаны первые {MAX_LIST_ENTRIES} из {len(entries)} ..."
    return _truncate(result)


def file_info(path: str) -> str:
    """Выводит информацию о файле: размер, владелец, права доступа, время изменения.

    Args:
        path: Путь к файлу или каталогу.

    Returns:
        Сведения о файле или сообщение об ошибке.
    """
    target = Path(path).expanduser()
    try:
        st = target.stat()
    except OSError as error:
        return f"Не удалось получить информацию о {path}: {error}"

    kind = "каталог" if target.is_dir() else "файл"
    changed = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    return (
        f"Путь: {target}\n"
        f"Тип: {kind}\n"
        f"Размер: {st.st_size} Б\n"
        f"Владелец: {_owner(st)}\n"
        f"Права: {stat.filemode(st.st_mode)}\n"
        f"Изменён: {changed}"
    )


def count_lines(path: str) -> str:
    """Быстро считает число строк в текстовом файле, читая его блоками.

    Args:
        path: Путь к текстовому файлу.

    Returns:
        Число строк или сообщение об ошибке.
    """
    target = Path(path).expanduser()
    newlines = 0
    size = 0
    last_byte = b""
    try:
        with target.open("rb") as file:
            while True:
                chunk = file.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                newlines += chunk.count(b"\n")
                last_byte = chunk[-1:]
    except OSError as error:
        return f"Не удалось прочитать файл {path}: {error}"

    lines = newlines + (1 if size and last_byte != b"\n" else 0)
    return f"Файл: {target}\nСтрок: {lines}\nРазмер: {size} Б"


def read_file(path: str) -> str:
    """Читает весь файл целиком с обрезкой длинного вывода.

    Args:
        path: Путь к текстовому файлу.

    Returns:
        Содержимое файла (при необходимости обрезанное) или сообщение об ошибке.
    """
    target = Path(path).expanduser()
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"Не удалось прочитать файл {path}: {error}"
    return _truncate(text)


def read_lines(path: str, start: int, end: int) -> str:
    """Читает строки файла в указанном диапазоне, позволяя читать файл по частям.

    Args:
        path: Путь к текстовому файлу.
        start: Номер первой строки, начиная с 1.
        end: Номер последней строки включительно.

    Returns:
        Строки с номерами или сообщение об ошибке.
    """
    if start < 1 or end < start:
        return "Некорректный диапазон строк: start должен быть >= 1 и <= end."

    target = Path(path).expanduser()
    selected = []
    try:
        with target.open(encoding="utf-8", errors="replace") as file:
            for number, line in enumerate(file, 1):
                if number > end:
                    break
                if number >= start:
                    selected.append(f"{number}: {line.rstrip()}")
    except OSError as error:
        return f"Не удалось прочитать файл {path}: {error}"

    if not selected:
        return f"В файле {path} нет строк в диапазоне {start}-{end}."
    return _truncate("\n".join(selected))


def search_file(path: str, pattern: str) -> str:
    """Ищет строки файла, соответствующие регулярному выражению.

    Args:
        path: Путь к текстовому файлу.
        pattern: Регулярное выражение Python для поиска.

    Returns:
        Найденные строки с номерами или сообщение об отсутствии совпадений.
    """
    try:
        regex = re.compile(pattern)
    except re.error as error:
        return f"Некорректное регулярное выражение: {error}"

    target = Path(path).expanduser()
    matches = []
    try:
        with target.open(encoding="utf-8", errors="replace") as file:
            for number, line in enumerate(file, 1):
                if regex.search(line):
                    matches.append(f"{number}: {line.rstrip()}")
                    if len(matches) >= MAX_SEARCH_MATCHES:
                        break
    except OSError as error:
        return f"Не удалось прочитать файл {path}: {error}"

    if not matches:
        return f"Совпадений не найдено: {pattern}"
    return _truncate(f"Найдено совпадений: {len(matches)}\n" + "\n".join(matches))


def create_file(path: str, content: str = "") -> str:
    """Создаёт новый файл с указанным содержимым, не перезаписывая существующий.

    Args:
        path: Путь к создаваемому файлу.
        content: Начальное текстовое содержимое, по умолчанию пусто.

    Returns:
        Сообщение о результате.
    """
    target = Path(path).expanduser()
    if target.exists():
        return f"Файл уже существует: {target}. Для перезаписи используйте write_file."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    except OSError as error:
        return f"Не удалось создать файл {path}: {error}"
    return f"Создан файл: {target} ({len(content)} символов)"


def write_file(path: str, content: str) -> str:
    """Полностью перезаписывает файл указанным содержимым.

    Args:
        path: Путь к файлу.
        content: Новое содержимое файла целиком.

    Returns:
        Сообщение о результате.
    """
    target = Path(path).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    except OSError as error:
        return f"Не удалось записать файл {path}: {error}"
    return f"Записан файл: {target} ({len(content)} символов)"


def replace_text(path: str, old: str, new: str) -> str:
    """Заменяет все вхождения подстроки в файле, не переписывая его целиком вручную.

    Args:
        path: Путь к текстовому файлу.
        old: Искомая подстрока.
        new: Подстрока замены.

    Returns:
        Число выполненных замен или сообщение об ошибке.
    """
    if not old:
        return "Искомая подстрока не может быть пустой."

    target = Path(path).expanduser()
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"Не удалось прочитать файл {path}: {error}"

    count = text.count(old)
    if not count:
        return f"Подстрока не найдена в {target}."
    try:
        target.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    except OSError as error:
        return f"Не удалось записать файл {path}: {error}"
    return f"Выполнено замен: {count} в {target}"


def append_file(path: str, content: str) -> str:
    """Дописывает текст в конец файла, создавая его при необходимости.

    Args:
        path: Путь к текстовому файлу.
        content: Добавляемый текст.

    Returns:
        Сообщение о результате.
    """
    target = Path(path).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8", newline="\n") as file:
            file.write(content)
    except OSError as error:
        return f"Не удалось дописать файл {path}: {error}"
    return f"Дописано {len(content)} символов в {target}"


def replace_lines(path: str, start: int, end: int, content: str) -> str:
    """Заменяет строки в указанном диапазоне новым содержимым.

    Args:
        path: Путь к текстовому файлу.
        start: Номер первой заменяемой строки, начиная с 1.
        end: Номер последней заменяемой строки включительно.
        content: Новый текст; пустая строка удаляет указанные строки.

    Returns:
        Сообщение о результате.
    """
    if start < 1 or end < start:
        return "Некорректный диапазон строк: start должен быть >= 1 и <= end."

    target = Path(path).expanduser()
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError as error:
        return f"Не удалось прочитать файл {path}: {error}"

    if start > len(lines):
        return f"В файле {target} только {len(lines)} строк."

    block = []
    if content:
        block = [content if content.endswith("\n") else content + "\n"]
    new_lines = lines[:start - 1] + block + lines[end:]

    try:
        target.write_text("".join(new_lines), encoding="utf-8", newline="\n")
    except OSError as error:
        return f"Не удалось записать файл {path}: {error}"
    return f"Заменены строки {start}-{end} в {target}"


def delete_file(path: str) -> str:
    """Удаляет файл.

    Args:
        path: Путь к удаляемому файлу.

    Returns:
        Сообщение о результате.
    """
    target = Path(path).expanduser()
    if target.is_dir():
        return f"Это каталог: {target}. Для каталогов используйте remove_directory."
    try:
        target.unlink()
    except OSError as error:
        return f"Не удалось удалить файл {path}: {error}"
    return f"Удалён файл: {target}"


def copy_file(source: str, destination: str) -> str:
    """Копирует файл в указанное место.

    Args:
        source: Путь к исходному файлу.
        destination: Путь назначения; если это каталог, файл копируется в него.

    Returns:
        Сообщение о результате.
    """
    src = Path(source).expanduser()
    dst = Path(destination).expanduser()
    try:
        if dst.is_dir():
            dst = dst / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError as error:
        return f"Не удалось скопировать {source} в {destination}: {error}"
    return f"Скопировано: {src} -> {dst}"


def move_file(source: str, destination: str) -> str:
    """Перемещает или переименовывает файл.

    Args:
        source: Путь к исходному файлу.
        destination: Путь назначения; если это каталог, файл перемещается в него.

    Returns:
        Сообщение о результате.
    """
    src = Path(source).expanduser()
    dst = Path(destination).expanduser()
    try:
        if dst.is_dir():
            dst = dst / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    except OSError as error:
        return f"Не удалось переместить {source} в {destination}: {error}"
    return f"Перемещено: {src} -> {dst}"


def make_directory(path: str) -> str:
    """Создаёт каталог вместе со всеми отсутствующими родительскими каталогами.

    Args:
        path: Путь к создаваемому каталогу.

    Returns:
        Сообщение о результате.
    """
    target = Path(path).expanduser()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return f"Не удалось создать каталог {path}: {error}"
    return f"Создан каталог: {target}"


def remove_directory(path: str, recursive: bool = False) -> str:
    """Удаляет каталог, при необходимости вместе со всем содержимым.

    Args:
        path: Путь к удаляемому каталогу.
        recursive: Удалять ли содержимое рекурсивно, по умолчанию нет.

    Returns:
        Сообщение о результате.
    """
    target = Path(path).expanduser()
    if not target.is_dir():
        return f"Не каталог: {target}"
    try:
        if recursive:
            shutil.rmtree(target)
        else:
            target.rmdir()
    except OSError as error:
        return f"Не удалось удалить каталог {path}: {error}"
    return f"Удалён каталог: {target}"


def find_files(path: str = ".", pattern: str = "*") -> str:
    """Рекурсивно ищет файлы и каталоги по шаблону имени.

    Args:
        path: Каталог, с которого начинается поиск, по умолчанию текущий.
        pattern: Шаблон glob, например *.py или config*.

    Returns:
        Найденные пути или сообщение об отсутствии совпадений.
    """
    root = Path(path).expanduser()
    if not root.is_dir():
        return f"Не каталог: {path}"

    found = []
    try:
        for entry in root.rglob(pattern):
            found.append(str(entry))
            if len(found) >= MAX_LIST_ENTRIES:
                break
    except OSError as error:
        return f"Ошибка поиска в {path}: {error}"

    if not found:
        return f"Ничего не найдено по шаблону {pattern} в {root}."
    result = f"Найдено: {len(found)}\n" + "\n".join(found)
    return _truncate(result)


def search_in_files(path: str = ".", pattern: str = "", mask: str = "*") -> str:
    """Ищет регулярное выражение в файлах каталога рекурсивно.

    Args:
        path: Каталог поиска, по умолчанию текущий.
        pattern: Регулярное выражение Python.
        mask: Маска имён файлов, например *.py, по умолчанию все файлы.

    Returns:
        Совпадения в виде файл:строка: текст или сообщение об их отсутствии.
    """
    try:
        regex = re.compile(pattern)
    except re.error as error:
        return f"Некорректное регулярное выражение: {error}"

    root = Path(path).expanduser()
    if not root.is_dir():
        return f"Не каталог: {path}"

    matches = []
    for file in root.rglob(mask):
        if not file.is_file():
            continue
        try:
            with file.open(encoding="utf-8", errors="strict") as stream:
                for number, line in enumerate(stream, 1):
                    if regex.search(line):
                        matches.append(f"{file}:{number}: {line.rstrip()}")
                        if len(matches) >= MAX_SEARCH_MATCHES:
                            return _truncate(f"Найдено совпадений: {len(matches)}\n" + "\n".join(matches))
        except (OSError, UnicodeDecodeError):
            continue

    if not matches:
        return f"Совпадений не найдено: {pattern}"
    return _truncate(f"Найдено совпадений: {len(matches)}\n" + "\n".join(matches))


FILE_TOOLS = [
    get_cwd,
    change_directory,
    list_files,
    file_info,
    count_lines,
    read_file,
    read_lines,
    search_file,
    create_file,
    write_file,
    replace_text,
    append_file,
    replace_lines,
    delete_file,
    copy_file,
    move_file,
    make_directory,
    remove_directory,
    find_files,
    search_in_files,
]

TOOLS = [get_system_time, run_powershell, run_shell, *FILE_TOOLS]
