"""
This module exposes the core bitfinex clients which includes both
a websocket client and a rest interface client
"""
from __future__ import absolute_import

from .ws.bitfinex.bfx_websocket import BfxWebsocket
from market_maker.utils.bitfinex.decimal_to_precision import decimal_to_precision
from market_maker.utils.bitfinex.decimal_to_precision import precision_from_string
from market_maker.utils.bitfinex.decimal_to_precision import DECIMAL_PLACES, TRUNCATE, ROUND, ROUND_UP, ROUND_DOWN
from market_maker.utils.bitfinex.decimal_to_precision import number_to_string
from market_maker.utils.bitmex.math import toNearest
from future.utils import iteritems
from market_maker.settings import settings
from market_maker.models.bitfinex import Order
from market_maker.rest.bitfinex import ClientV1 as Client1
from market_maker.rest.bitfinex import ClientV2 as Client2
from market_maker.utils.bitmex import errors

import requests
from time import sleep
import datetime
import json
import base64
import uuid
import logging
import decimal
import time
from market_maker.exchange import BaseExchange

WS_HOST = 'wss://api.bitfinex.com/ws/2'

API_KEY = "DvG4Fhfr7J7QuHQMdXicqCd5w0970dkN94A5qMgGBvD"
API_SECRET = "X96D8w1EdpSrMQvhoTq0WFSEmb4i1SdtiOAmuZcsiSu"

class BitfinexClient:
    """
    The Bitfinex client exposes REST and websocket objects
    """
    def __init__(self, API_KEY=None, API_SECRET=None, ws_host=WS_HOST, create_event_emitter=None, logLevel='INFO',
                 dead_man_switch=False, ws_capacity=25, *args, **kwargs):
        self.rest1 = Client1(API_KEY, API_SECRET)
        self.rest2 = Client2(API_KEY, API_SECRET)
        self.ws = BfxWebsocket(API_KEY=API_KEY, API_SECRET=API_SECRET, host=ws_host,
                               logLevel=logLevel, dead_man_switch=dead_man_switch,
                               ws_capacity=ws_capacity, create_event_emitter=create_event_emitter, *args, **kwargs)

bfx = BitfinexClient(
    API_KEY=API_KEY,
    API_SECRET=API_SECRET,
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
        print("Error: {}".format(err))

    def get_tick_size(self, instrument):
        bid = number_to_string(instrument['bid'])
        bid_precision = precision_from_string(bid)
        ask = number_to_string(instrument['ask'])
        ask_precision = precision_from_string(ask)
        high = number_to_string(instrument['high'])
        high_precision = precision_from_string(high)
        low = number_to_string(instrument['low'])
        low_precision = precision_from_string(low)
        precision = max(bid_precision, ask_precision, high_precision, low_precision)
        if precision == 0:
            return 1
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
        self.ws.exit()

    #
    # Public methods
    #
    def ticker_data(self, symbol=None):
        '''Return a ticker object. Generated from instrument.'''
        instrument = self.instrument(symbol)

        bid = instrument['bid'] or instrument['last_price']
        ask = instrument['ask'] or instrument['last_price']
        ticker = {
            "last": instrument['last_price'],
            "buy": bid,
            "sell": ask,
            "mid": (bid + ask) / 2
        }

        # The instrument has a tickSize. Use it to round values.
        return {k: toNearest(float(v or 0), instrument['tickSize']) for k, v in iteritems(ticker)}

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

    def funds(self):
        """Get your current balance."""
        wallets = bfx.ws.wallets.get_wallets()
        quote_currency = self.symbol[-3:]
        for w in wallets:
            if w.type == "margin" and w.currency == quote_currency:
                return {'walletBalance': w.balance, 'marginBalance': 0}

        return {'walletBalance': 0, 'marginBalance': 0}

    def position(self, symbol):
        """Get your open position."""
        position = bfx.ws.positionManager.get_open_positions().get(symbol)
        if position is None:
            # No position found; stub it
            return {'avgCostPrice': 0, 'avgEntryPrice': 0, 'currentQty': 0, 'symbol': symbol}

        return {'avgCostPrice': 0, 'avgEntryPrice': position.base_price, 'currentQty': position.amount, 'symbol': symbol}

    def create_bulk_orders(self, orders):
        """Create multiple orders."""
        for order in orders:
            order['clOrdID'] = self.orderIDPrefix + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n')
            order['symbol'] = self.symbol
            if self.postOnly:
                order['execInst'] = 'ParticipateDoNotInitiate'
        return self._curl_bitmex(path='order/bulk', postdict={'orders': orders}, verb='POST', max_retries=self.max_retries)

    def amend_bulk_orders(self, orders):
        """Amend multiple orders."""
        # Note rethrow; if this fails, we want to catch it and re-tick
        return self._curl_bitmex(path='order/bulk', postdict={'orders': orders}, verb='PUT', rethrow_errors=True, max_retries=self.max_retries)

    def open_orders(self):
        """Get open orders."""
        return bfx.ws.orderManager.get_open_orders()

    def http_open_orders(self):
        raw_orders = bfx.rest2.active_orders(self.symbol)
        return [Order.from_raw_order(o) for o in raw_orders]

    def cancel_orders(self, orders):
        """Cancel existing orders."""
        order_ids = [o.id for o in orders]
        return bfx.rest1.delete_multiple_orders(order_ids)

