from __future__ import absolute_import
from abc import abstractmethod

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
    def cancel(self, orderID):
        pass

