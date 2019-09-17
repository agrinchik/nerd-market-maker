
import logging

class WsData_Storage:

    def __init__(self):
        self.logger = logging.getLogger('root')
        self.tickers = {}
        self.candles = {}
        self.trades = {}
        self.info = {}
        self.margin_info = {}

    def put_ticker(self, symbol, ticker):
        self.tickers[symbol] = ticker

    def get_ticker(self, symbol):
        return self.tickers.get(symbol)

    def put_info(self, info_data):
        self.info['info'] = info_data

    def get_info(self):
        return self.info.get('info')

    def put_margin_info(self, calc_name, info):
        self.margin_info[calc_name] = info

    def get_margin_info(self, calc_name):
        return self.margin_info.get(calc_name)

    def get_symbol_margin_info(self, symbol):
        return self.margin_info.get("sym_{}".format(symbol))

    def is_initialized(self):
        return len(self.tickers.keys()) > 0 and len(self.info.keys()) > 0  # TODO: Add other criteria


