import logging
import requests
from market_maker.settings import settings


def setup_custom_logger(name, log_level=settings.LOG_LEVEL):
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    #logging.basicConfig(filename=settings.LOG_FILENAME, filemode='a', format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    logger.addHandler(handler)
    return logger


def get_telegram_message_text(bot_id, txt):
    return "<b>{}</b>: {}".format(bot_id, txt)


def send_telegram_message(message=""):
    base_url = "https://api.telegram.org/bot{}".format(settings.TELEGRAM_BOT_APIKEY)
    #print("Sending message to Telegram: {}".format(message))
    return requests.get("{}/sendMessage".format(base_url), params={
        'chat_id': settings.TELEGRAM_CHANNEL,
        'text': message,
        'parse_mode': 'html'  # or html
    })


def log_info(logger, log_txt, send_telegram=False):
    logger.info(log_txt)
    if settings.LOG_TO_TELEGRAM is True and send_telegram is True:
        send_telegram_message(log_txt)


def log_error(logger, log_txt, send_telegram=False):
    logger.error(log_txt)
    if settings.LOG_TO_TELEGRAM is True and send_telegram is True:
        send_telegram_message(log_txt)
