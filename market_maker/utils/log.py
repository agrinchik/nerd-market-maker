import logging
import requests
from market_maker.settings import settings
from common.bot_info import BotInfo


def setup_bot_custom_logger(name, log_level=settings.LOG_LEVEL):
    botId = settings.BOTID
    log_text_format = "%(asctime)s - {} - %(levelname)s - %(module)s - %(message)s".format(botId)
    formatter = logging.Formatter(fmt=log_text_format)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    log_filename = "./logs/{}/{}_{}".format(settings.ENV.lower(), settings.BOTID.lower(), settings.LOG_FILENAME)
    logging.basicConfig(filename=log_filename, filemode='a', format=log_text_format)
    #logger.addHandler(handler)
    return logger


def setup_supervisor_custom_logger(name, log_level=settings.LOG_LEVEL):
    log_text_format = "%(asctime)s  - %(levelname)s - %(module)s - %(message)s"
    formatter = logging.Formatter(fmt=log_text_format)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    log_filename = "./logs/{}/nerd_supervisor_log_out.txt".format(settings.ENV.lower())
    logging.basicConfig(filename=log_filename, filemode='a', format=log_text_format)
    #logger.addHandler(handler)
    return logger


def get_telegram_message_text(txt):
    instance_id = BotInfo.parse_for_tg_logs(settings.BOTID) if settings.BOTID else settings.INSTANCEID
    return "<b>{} - {}</b>:\n{}".format(instance_id, settings.ENV, txt)


def send_telegram_message(message=""):
    base_url = "https://api.telegram.org/bot{}".format(settings.TELEGRAM_BOT_APIKEY)
    telegram_msg = get_telegram_message_text(message)
    #print("Sending message to Telegram: {}".format(telegram_msg))
    return requests.get("{}/sendMessage".format(base_url), params={
        'chat_id': settings.TELEGRAM_CHANNEL,
        'text': telegram_msg,
        'parse_mode': 'html'  # or html
    })

def log_debug(logger, log_txt, send_telegram=False):
    logger.debug(log_txt)
    if settings.LOG_TO_TELEGRAM is True and send_telegram is True:
        send_telegram_message(log_txt)

def log_info(logger, log_txt, send_telegram=False):
    logger.info(log_txt)
    if settings.LOG_TO_TELEGRAM is True and send_telegram is True:
        send_telegram_message(log_txt)


def log_error(logger, log_txt, send_telegram=False):
    logger.error(log_txt)
    if settings.LOG_TO_TELEGRAM is True and send_telegram is True:
        send_telegram_message(log_txt)
