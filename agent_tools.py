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
