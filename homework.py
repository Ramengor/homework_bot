import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import (BotTokenException, APIError, InvalidAPIResponseError,
                        UnknownHomeworkStatusError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', mode='w')
    ]
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, value in tokens.items() if not value]
    if missing_tokens:
        logging.critical(f"Не все переменные окружения доступны: "
                         f"{', '.join(missing_tokens)}"
                         )
        raise BotTokenException('Не все переменные окружения доступны.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        logging.debug(f'Отправка сообщения в чат {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено в чат {message}')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ в виде Python-объекта."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise APIError(
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа: {response.status_code}'
            )
        return response.json()
    except requests.RequestException as req_err:
        raise APIError(f'Ошибка при запросе к API: {req_err}')


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        raise TypeError(f'Ответ API должен быть словарём, '
                        f'получен {type(response)}'
                        )
    if 'homeworks' not in response:
        raise KeyError('Поле "homeworks" отсутствует')
    if 'current_date' not in response:
        raise KeyError('Поле "current_date" отсутствует')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(f'Поле "homeworks" должно быть списком, '
                        f'получен {type(homeworks)}'
                        )
    logging.debug('Ответ API прошёл проверку')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        raise InvalidAPIResponseError('Поле "homework_name" отсутствует')
    if 'status' not in homework:
        raise InvalidAPIResponseError('Поле "status" отсутствует')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        raise UnknownHomeworkStatusError(
            f'Неизвестный статус работы: {homework_status}'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.info(f'Сформировано сообщение о статусе: {homework_name}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logging.debug('Нет новых статусов домашних работ')

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
