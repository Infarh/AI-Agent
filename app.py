import ctypes
import sys

import ollama

if sys.platform == "win32":  # включает ANSI-цвета в консоли Windows
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

MODEL = "qwen2.5-coder:7b"
SYSTEM_PROMPT = "Ты — полезный ассистент-программист. Отвечай на русском языке, кратко и по делу."
GRAY = "\033[90m"
RESET = "\033[0m"

messages = [{"role": "system", "content": SYSTEM_PROMPT}]

while True:
    prompt = input("Вы: ").strip()
    if prompt in ("/exit", "/quit"):
        break
    if not prompt:
        continue

    messages.append({"role": "user", "content": prompt})

    print("Модель: ", end="", flush=True)
    answer = ""
    for chunk in ollama.chat(model=MODEL, messages=messages, stream=True):
        message = chunk["message"]
        if message.thinking:
            print(f"{GRAY}{message.thinking}{RESET}", end="", flush=True)
        piece = message.content or ""
        answer += piece
        print(piece, end="", flush=True)
    print("\n")

    messages.append({"role": "assistant", "content": answer})

