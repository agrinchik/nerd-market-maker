from __future__ import absolute_import
from abc import abstractmethod
from market_maker.settings import settings


class BaseExchange(object):

    def __init__(self):
        pass

    @abstractmethod
    def exit(self):
        pass

    #
    # Public methods
    #
    @abstractmethod
    def ticker_data(self, symbol=None):
        pass

    @abstractmethod
    def is_open(self):
        pass

    @abstractmethod
    def instrument(self, symbol):
        pass

    @abstractmethod
    def funds(self):
        pass

    @abstractmethod
    def position(self, symbol):
        pass

    @abstractmethod
    def create_bulk_orders(self, orders):
        pass

    @abstractmethod
    def amend_bulk_orders(self, orders):
        pass

    @abstractmethod
    def open_orders(self):
        pass

    @abstractmethod
    def http_open_orders(self):
        pass

    @abstractmethod
    def cancel_orders(self, orders):
        pass


BITMEX = 1
BITFINEX = 2


EXCHANGE_CONFIG = {
    "bitmex": {
        "id": BITMEX
    },
    "bitfinex": {
        "id": BITFINEX
    }
}


class ExchangeInfo(object):
    @staticmethod
    def resolve_exchange():
        exchange_str = settings.EXCHANGE
        entry = EXCHANGE_CONFIG.get(exchange_str.lower())
        if entry is not None:
            return entry["id"]
        else:
            raise Exception("Unable to resolve exchange name: {}".format(exchange_str))

    @staticmethod
    def get_exchange_name():
        exchange_str = settings.EXCHANGE
        return exchange_str

    @staticmethod
    def is_bitmex():
        exchange_id = ExchangeInfo.resolve_exchange()
        return exchange_id == BITMEX

    @staticmethod
    def is_bitfinex():
        exchange_id = ExchangeInfo.resolve_exchange()
        return exchange_id == BITFINEX

    @staticmethod
    def get_apikey():
        if ExchangeInfo.is_bitmex():
            return settings.BITMEX_API_KEY
        if ExchangeInfo.is_bitfinex():
            return settings.BITFINEX_API_KEY

    @staticmethod
    def get_apisecret():
        if ExchangeInfo.is_bitmex():
            return settings.BITMEX_API_SECRET
        if ExchangeInfo.is_bitfinex():
            return settings.BITFINEX_API_SECRET
