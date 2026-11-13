import ctypes
import sys
import time

import ollama

from agent_tools import get_capabilities, get_models, pick_model

if sys.platform == "win32":  # включает ANSI-цвета в консоли Windows
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

MODEL = "qwen2.5-coder:7b"
OLLAMA_HOST = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:11434"
SYSTEM_PROMPT = "Ты — полезный ассистент-программист. Отвечай на русском языке, кратко и по делу."
GRAY = "\033[90m"
RESET = "\033[0m"


def set_title(text):
    """Выводит текст в заголовок окна консоли."""
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetConsoleTitleW(text)
    else:
        print(f"\033]0;{text}\007", end="", flush=True)


client = ollama.Client(host=OLLAMA_HOST)

print(f"Ollama: {OLLAMA_HOST}")
models = get_models(client)

print("Доступные модели:")
for i, name in enumerate(models, 1):
    capabilities = get_capabilities(client, name)
    flags = "".join(f" [{cap}]" for cap in ("thinking", "tools") if cap in capabilities)
    mark = " (по умолчанию)" if name == MODEL else ""
    print(f"  {i}. {name}{flags}{mark}")

for attempt in range(1, 4):
    choice = input(f"Выберите модель [1-{len(models)}] (Enter — {MODEL}): ")
    selected = pick_model(models, MODEL, choice)
    if selected is not None:
        MODEL = selected
        break
    if attempt < 3:
        print("Неверный номер модели, попробуйте ещё раз.")
else:
    print("Три неверных ввода подряд — завершение работы.")
    sys.exit(1)

print(f"Используется модель: {MODEL}\n")

messages = [{"role": "system", "content": SYSTEM_PROMPT}]

while True:
    prompt = input("Вы: ").strip()
    if prompt in ("/exit", "/quit"):
        break
    if not prompt:
        continue

    messages.append({"role": "user", "content": prompt})

    answer = ""
    tokens = 0
    start = None
    thinking_started = False
    answer_started = False
    for chunk in client.chat(model=MODEL, messages=messages, stream=True):
        message = chunk["message"]
        piece = message.content or ""

        if message.thinking:
            if not thinking_started:
                print("Thinking: ", end="", flush=True)
                thinking_started = True
            print(f"{GRAY}{message.thinking}{RESET}", end="", flush=True)

        if piece:
            if not answer_started:
                if thinking_started:
                    print()
                print("Модель: ", end="", flush=True)
                answer_started = True
            answer += piece
            print(piece, end="", flush=True)

        if message.thinking or piece:
            if start is None:
                start = time.perf_counter()
            tokens += 1
            elapsed = time.perf_counter() - start
            if elapsed >= 0.5:
                set_title(f"{MODEL} — {tokens / elapsed:.1f} ток/с")

    print("\n")
    if chunk.eval_count and chunk.eval_duration:
        set_title(f"{MODEL} — {chunk.eval_count / (chunk.eval_duration / 1e9):.1f} ток/с")

    messages.append({"role": "assistant", "content": answer})

