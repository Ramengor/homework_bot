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
            logging.error(
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа API: {response.status_code}'
            )
            raise APIError(
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа: {response.status_code}'
            )
        logging.info(f'Получен ответ от API: {response}')
        return response.json()
    except requests.RequestException as req_err:
        logging.error(f'Ошибка при запросе к API: {req_err}')
        raise APIError(f'Ошибка при запросе к API: {req_err}')


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        logging.error('Ответ API должен быть словарём')
        raise TypeError('Ответ API должен быть словарём')
    if 'homeworks' not in response or 'current_date' not in response:
        logging.error('В ответе API отсутствуют необходимые ключи')
        raise TypeError('В ответе API отсутствуют необходимые ключи')
    if not isinstance(response['homeworks'], list):
        logging.error('Поле "homeworks" должно быть списком')
        raise TypeError('Поле "homeworks" должно быть списком')
    logging.debug('Ответ API прошёл проверку')
    return response['homeworks']


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is None or homework_status is None:
        logging.error('В ответе отсутствуют необходимые поля')
        raise InvalidAPIResponseError('В ответе отсутствуют необходимые поля')

    if homework_status not in HOMEWORK_VERDICTS:
        logging.error(f'Неожиданный статус работы: {homework_status}')
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
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
