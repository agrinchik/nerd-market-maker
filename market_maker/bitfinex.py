"""
This module exposes the core bitfinex clients which includes both
a websocket client and a rest interface client
"""
from __future__ import absolute_import

from .ws.bitfinex.bfx_websocket import BfxWebsocket
from market_maker.utils.bitfinex.decimal_to_precision import precision_from_string
from market_maker.utils.bitfinex.decimal_to_precision import number_to_string
from market_maker.utils.bitmex.math import toNearest
from future.utils import iteritems
from market_maker.models.bitfinex import Order, OrderType
from market_maker.rest.bitfinex import ClientV1 as Client1
from market_maker.rest.bitfinex import ClientV2 as Client2
from market_maker.exchange import ExchangeInfo
from market_maker.settings import settings
from market_maker.utils.bitfinex.utils import strip_trade_symbol
from market_maker.dynamic_settings import BITFINEX_DEFAULT_LEVERAGE

import math
from time import sleep
import logging
import decimal
from market_maker.exchange import BaseExchange



WS_HOST = 'wss://api.bitfinex.com/ws/2'

API_KEY = "DvG4Fhfr7J7QuHQMdXicqCd5w0970dkN94A5qMgGBvD"
API_SECRET = "X96D8w1EdpSrMQvhoTq0WFSEmb4i1SdtiOAmuZcsiSu"

class BitfinexClient:
    """
    The Bitfinex client exposes REST and websocket objects
    """
    def __init__(self, symbol=None, API_KEY=None, API_SECRET=None, ws_host=WS_HOST, create_event_emitter=None, logLevel='INFO',
                 dead_man_switch=False, ws_capacity=25, *args, **kwargs):
        self.rest1 = Client1(API_KEY, API_SECRET)
        self.rest2 = Client2(API_KEY, API_SECRET)
        self.ws = BfxWebsocket(symbol=symbol, API_KEY=API_KEY, API_SECRET=API_SECRET, host=ws_host,
                               logLevel=logLevel, dead_man_switch=dead_man_switch,
                               ws_capacity=ws_capacity, create_event_emitter=create_event_emitter, *args, **kwargs)


bfx = BitfinexClient(
    symbol=settings.SYMBOL,
    API_KEY=ExchangeInfo.get_apikey(),
    API_SECRET=ExchangeInfo.get_apisecret(),
    logLevel='INFO'
)


# https://docs.bitfinex.com/v2/docs/ws-general
class Bitfinex(BaseExchange):

    """Bitfinex API Connector.
       The connector exposes rest and websocket objects
    """
    def __init__(self, symbol=None):
        self.logger = logging.getLogger('root')

        super().__init__()
        self.symbol = symbol

        bfx.ws.on('connected', self.start)
        bfx.ws.run()

        self.logger.info('Connected to WS. Waiting for data images, this may take a moment...')

        # Connected. Wait for snapshots
        self.__wait_for_symbol(symbol)
        self.logger.info('********* Got all market data. Starting! *********')

    def __wait_for_symbol(self, symbol):
        '''On subscribe, this data will come down. Wait for it.'''
        while not bfx.ws.is_data_initialized():
            self.logger.info('__wait_for_symbol ....')
            sleep(0.4)

    @bfx.ws.on('error')
    def log_error(err):
        logger = logging.getLogger('root')
        logger.info("Error: {}".format(err))

    def get_tick_size(self, instrument):
        bid_price = number_to_string(instrument['bidPrice'])
        bid_precision = precision_from_string(bid_price)
        ask_price = number_to_string(instrument['askPrice'])
        ask_precision = precision_from_string(ask_price)
        last_price = number_to_string(instrument['lastPrice'])
        last_precision = precision_from_string(last_price)
        precision = max(bid_precision, ask_precision, last_precision)
        if precision == 0:
            return 0
        else:
            if instrument['lastPrice'] > 1 and precision > 5:
                return 5 - (int(math.log10(instrument['lastPrice'])) + 1)
            else:
                return round(pow(10, -precision), precision)

    async def start(self):
        # await bfx.ws.subscribe('candles', 'tBTCUSD', timeframe='1m')
        # await self.bfx.ws.subscribe('trades', 'tBTCUSD')
        await bfx.ws.subscribe('ticker', self.symbol)
        self.logger.info('START - subscribed!')

    def __del__(self):
        self.exit()

    def exit(self):
        #TODO: Reimplement
        pass

    #
    # Public methods
    #
    def ticker_data(self, symbol=None):
        '''Return a ticker object. Generated from instrument.'''
        instrument = self.instrument(symbol)

        bid = instrument['bidPrice'] or instrument['lastPrice']
        ask = instrument['askPrice'] or instrument['lastPrice']
        ticker = {
            "last": instrument['lastPrice'],
            "buy": bid,
            "sell": ask,
            "mid": (bid + ask) / 2
        }

        # The instrument has a tickSize. Use it to round values.
        result = {k: toNearest(float(v or 0), instrument['tickSize']) for k, v in iteritems(ticker)}
        self.logger.info('Ticker: {}'.format(result))
        return result

    def is_open(self):
        """Check that websockets are still open."""
        return not bfx.ws.is_disconnected_socket()

    def instrument(self, symbol):
        """Get an instrument's details."""
        instrument = bfx.ws.wsdata.get_ticker(symbol)
        if instrument is None:
            raise Exception("Unable to find instrument with symbol: " + symbol)
        # Turn the 'tickSize' into 'tickLog' for use in rounding
        # http://stackoverflow.com/a/6190291/832202
        instrument['tickSize'] = self.get_tick_size(instrument)
        instrument['tickLog'] = decimal.Decimal(str(instrument['tickSize'])).as_tuple().exponent * -1
        return instrument

    def calculate_margin_balance(self, symbol):
        symbol_margin_info = bfx.ws.wsdata.get_symbol_margin_info(symbol)
        return symbol_margin_info["user_pl"] / BITFINEX_DEFAULT_LEVERAGE if symbol_margin_info is not None else 0

    def funds(self):
        """Get wallet balance."""
        wallets = bfx.ws.wallets.get_wallets()
        quote_currency = self.symbol[-3:]
        for w in wallets:
            if w.type == "margin" and w.currency == quote_currency:
                """Get margin balance."""
                walletBalance = w.balance
                marginBalance = self.calculate_margin_balance(self.symbol)
                return {'walletBalance': walletBalance, 'marginBalance': marginBalance}

        return {'walletBalance': 0, 'marginBalance': 0}

    def position(self, symbol):
        """Get your open position."""
        position = bfx.ws.positionManager.get_open_positions().get(symbol)
        if position is None:
            # No position found; stub it
            return {'avgCostPrice': 0, 'avgEntryPrice': 0, 'currentQty': 0, 'symbol': symbol}

        return position

    def create_bulk_orders(self, orders):
        self.logger.info('Creating multiple orders: {}'.format(orders))
        new_orders = []
        """Create multiple orders."""
        for order in orders:
            new_order = {
                "symbol": strip_trade_symbol(self.symbol),
                "amount": str(order["orderQty"]),
                "price": str(order["price"]),
                "exchange": ExchangeInfo.get_exchange_name(),
                "side": order['side'].lower(),
                "type": OrderType.LIMIT.lower()
            }
            new_orders.append(new_order)

        response = bfx.rest1.place_multiple_orders(new_orders)
        self.logger.info('Creating multiple orders - response: {}'.format(response))
        return response

    def amend_bulk_orders(self, orders):
        """Amend multiple orders."""
        self.logger.info('Amending multiple orders: cancelling and creating new orders: {}'.format(orders))
        self.cancel_orders(orders)
        sleep(settings.API_REST_INTERVAL)
        return self.create_bulk_orders(orders)

    def open_orders(self):
        """Get open orders."""
        return bfx.ws.orderManager.get_open_orders()

    def http_open_orders(self):
        raw_orders = bfx.rest2.active_orders(self.symbol)
        return [Order.from_raw_order(o) for o in raw_orders]

    def cancel_orders(self, orders):
        """Cancel existing orders."""
        self.logger.info('Cancelling multiple orders: {}'.format(orders))
        order_ids = [o["orderID"] for o in orders]
        return bfx.rest1.delete_multiple_orders(order_ids)

