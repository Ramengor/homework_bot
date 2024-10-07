class BotTokenException(Exception):
    """Ошибка, связанная с доступностью переменных окружения."""
    pass


class APIError(Exception):
    """Ошибка, связанная с запросом к API."""
    pass


class InvalidAPIResponseError(Exception):
    """Ошибка некорректного ответа от API."""
    pass


class UnknownHomeworkStatusError(Exception):
    """Неизвестный статус домашней работы."""
    pass
