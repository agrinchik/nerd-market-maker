
class WsData_Storage:

    def __init__(self):
        self.tickers = {}
        self.candles = {}
        self.trades = {}
        self.info = {}

    def put_ticker(self, symbol, ticker):
        self.tickers[symbol] = ticker

    def get_ticker(self, symbol):
        return self.tickers.get(symbol)

    def put_info(self, info_data):
        self.info['info'] = info_data

    def get_info(self):
        return self.info.get('info')

    def is_initialized(self):
        return len(self.tickers.keys()) > 0 and len(self.info.keys()) > 0  # TODO: Add other criteria


