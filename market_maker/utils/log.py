import logging
import requests
from market_maker.settings import settings
from common.robot_info import RobotInfo

LOG_TO_CONSOLE = True

class LoggerHolder:
    __logger = None

    @classmethod
    def get_instance(cls):
        return cls.__logger

    @classmethod
    def set_instance(cls, logger):
        if not cls.__logger:
            cls.__logger = logger


def setup_robot_custom_logger(name, log_level=settings.LOG_LEVEL):
    if LoggerHolder.get_instance():
        return LoggerHolder.get_instance()

    robotId = settings.ROBOTID
    log_text_format = "%(asctime)s - {} - %(levelname)s - %(module)s - %(message)s".format(robotId)
    formatter = logging.Formatter(fmt=log_text_format)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    level_name = logging.getLevelName(log_level)
    logger.setLevel(level_name)
    if not LOG_TO_CONSOLE:
        log_filename = "./logs/{}/{}_{}".format(settings.ENV.lower(), settings.ROBOTID.lower(), settings.LOG_FILENAME)
        logging.basicConfig(filename=log_filename, filemode='a', format=log_text_format)
    else:
        logger.addHandler(handler)
    LoggerHolder.set_instance(logger)
    return logger


def setup_supervisor_custom_logger(name, log_level=settings.SUPERVISOR_LOG_LEVEL):
    if LoggerHolder.get_instance():
        return LoggerHolder.get_instance()

    log_text_format = "%(asctime)s  - %(levelname)s - %(module)s - %(message)s"
    formatter = logging.Formatter(fmt=log_text_format)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    if not LOG_TO_CONSOLE:
        log_filename = "./logs/{}/nerd_supervisor_log_out.txt".format(settings.ENV.lower())
        logging.basicConfig(filename=log_filename, filemode='a', format=log_text_format)
    else:
        logger.addHandler(handler)
    LoggerHolder.set_instance(logger)
    return logger


def get_telegram_message_text(txt):
    instance_id = RobotInfo.parse_for_tg_logs(settings.ROBOTID) if settings.ROBOTID else settings.INSTANCEID
    return "<b>{} - {}</b>:\n{}".format(instance_id, settings.ENV.upper(), txt)


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
