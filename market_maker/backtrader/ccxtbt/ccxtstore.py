#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2017 Ed Bartosh <bartosh@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import time
from datetime import datetime, timedelta
from functools import wraps

import backtrader as bt
import ccxt
from backtrader.metabase import MetaParams
from backtrader.utils.py3 import with_metaclass
from ccxt.base.errors import NetworkError, ExchangeError, DDoSProtection
from market_maker.utils.log import send_telegram_message
from .ratelimits import RateLimitConfig
from market_maker.utils import log

logger = log.setup_supervisor_custom_logger('root')


class MetaSingleton(MetaParams):
    '''Metaclass to make a metaclassed class a singleton'''

    def __init__(cls, name, bases, dct):
        super(MetaSingleton, cls).__init__(name, bases, dct)
        cls._singleton = None

    def __call__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = (
                super(MetaSingleton, cls).__call__(*args, **kwargs))

        return cls._singleton


class CCXTStore(with_metaclass(MetaSingleton, object)):
    '''API provider for CCXT feed and broker classes.

    Added a new get_wallet_balance method. This will allow manual checking of the balance.
        The method will allow setting parameters. Useful for getting margin balances

    Added new private_end_point method to allow using any private non-unified end point

    '''

    RATE_LIMIT_ERROR_RECOVER_DELAY = 90
    # Supported granularities
    _GRANULARITIES = {
        (bt.TimeFrame.Minutes, 1): ('1m', timedelta(minutes=1)),
        (bt.TimeFrame.Minutes, 3): ('3m', timedelta(minutes=3)),
        (bt.TimeFrame.Minutes, 5): ('5m', timedelta(minutes=5)),
        (bt.TimeFrame.Minutes, 15): ('15m', timedelta(minutes=15)),
        (bt.TimeFrame.Minutes, 30): ('30m', timedelta(minutes=30)),
        (bt.TimeFrame.Minutes, 60): ('1h', timedelta(hours=1)),
        (bt.TimeFrame.Minutes, 90): ('90m', timedelta(hours=1, minutes=30)),
        (bt.TimeFrame.Minutes, 120): ('2h', timedelta(hours=2)),
        (bt.TimeFrame.Minutes, 180): ('3h', timedelta(hours=3)),
        (bt.TimeFrame.Minutes, 240): ('4h', timedelta(hours=4)),
        (bt.TimeFrame.Minutes, 360): ('6h', timedelta(hours=6)),
        (bt.TimeFrame.Minutes, 480): ('8h', timedelta(hours=8)),
        (bt.TimeFrame.Minutes, 720): ('12h', timedelta(hours=12)),
        (bt.TimeFrame.Days, 1): ('1d', timedelta(days=1)),
        (bt.TimeFrame.Days, 3): ('3d', timedelta(days=3)),
        (bt.TimeFrame.Weeks, 1): ('1w', timedelta(days=7)),
        (bt.TimeFrame.Weeks, 2): ('2w', timedelta(days=14)),
        (bt.TimeFrame.Months, 1): ('1M', timedelta(days=30)),
        (bt.TimeFrame.Months, 3): ('3M', timedelta(days=90)),
        (bt.TimeFrame.Months, 6): ('6M', timedelta(days=180)),
        (bt.TimeFrame.Years, 1): ('1y', timedelta(days=365)),
    }

    BrokerCls = None  # broker class will auto register
    DataCls = None  # data class will auto register

    @classmethod
    def getdata(cls, *args, **kwargs):
        '''Returns ``DataCls`` with args, kwargs'''
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        '''Returns broker with *args, **kwargs from registered ``BrokerCls``'''
        return cls.BrokerCls(*args, **kwargs)

    def __init__(self, cerebro, exchange, currency, config, retries, rate_limit_factor):
        self.cerebro = cerebro
        self.exchange = getattr(ccxt, exchange)(config)
        self.currency = currency
        self.retries = retries
        self.rate_limit_factor = rate_limit_factor
        balance = self.exchange.fetch_balance() if 'secret' in config else 0
        self._cash = 0 if balance == 0 else balance['free'][currency]
        self._value = 0 if balance == 0 else balance['total'][currency]

    def get_granularity(self, timeframe, compression):
        if not self.exchange.has['fetchOHLCV']:
            raise NotImplementedError("'%s' exchange doesn't support fetching OHLCV data" % \
                                      self.exchange.name)

        granularity = self._GRANULARITIES.get((timeframe, compression))
        if granularity is None:
            raise ValueError("backtrader CCXT module doesn't support fetching OHLCV "
                             "data for time frame %s, comression %s" % \
                             (bt.TimeFrame.getname(timeframe), compression))

        if self.exchange.timeframes and granularity[0] not in self.exchange.timeframes:
            raise ValueError("'%s' exchange doesn't support fetching OHLCV data for "
                             "%s time frame" % (self.exchange.name, granularity))

        return granularity

    def get_rate_limit_error_recover_delay(self, rateLimit):
        return int(self.RATE_LIMIT_ERROR_RECOVER_DELAY - rateLimit / 1000)

    def retry(method):
        @wraps(method)
        def retry_method(self, *args, **kwargs):
            rate_limit = RateLimitConfig.get_rate_limit(self.exchange.name, method.__name__, self.rate_limit_factor)
            for i in range(self.retries):
                logger.debug('{} - {} - Attempt {}'.format(datetime.now(), method.__name__, i))
                time.sleep(rate_limit / 1000)
                try:
                    return method(self, *args, **kwargs)
                except (NetworkError, ExchangeError) as err:
                    logger.debug("retry_method(): catched {}".format(type(err)))
                    if isinstance(err, DDoSProtection):
                        # Trying to recover from DDoSProtection exception - waiting for rate_limit_recover_delay seconds
                        rate_limit_recover_delay = self.get_rate_limit_error_recover_delay(rate_limit)
                        error_log = '{}(): Rate limit has been exceeded on the exchange. Waiting for additional {} seconds and trying to recover.'.format(method.__name__, rate_limit_recover_delay)
                        logger.debug(error_log)
                        send_telegram_message(error_log)
                        time.sleep(rate_limit_recover_delay)
                    if i == self.retries - 1:
                        raise

        return retry_method

    @retry
    def fetch_ticker(self, currency, params=None):
        ticker_data = self.exchange.fetch_ticker(currency, params)
        return ticker_data

    @retry
    def get_wallet_balance(self, currency, params=None):
        balance = self.exchange.fetch_balance(params)
        return balance

    @retry
    def get_balance(self):
        balance = self.exchange.fetch_balance()
        self._cash = balance['free'][self.currency]
        self._value = balance['total'][self.currency]

    @retry
    def getposition(self):
        return self._value
        # return self.getvalue(currency)

    @retry
    def create_order(self, symbol, order_type, side, amount, price, params):
        # returns the order
        return self.exchange.create_order(symbol=symbol, type=order_type, side=side, amount=amount, price=price, params=params)

    @retry
    def cancel_order(self, order_id, symbol):
        return self.exchange.cancel_order(order_id, symbol)

    @retry
    def fetch_trades(self, symbol):
        return self.exchange.fetch_trades(symbol)

    @retry
    def fetch_my_trades(self, symbol, since, limit, params={}):
        return self.exchange.fetch_my_trades(symbol, since, limit, params)

    @retry
    def fetch_ohlcv(self, symbol, timeframe, since, limit, params={}):
        since_val_epoch = since / 1000
        since_dt = datetime.fromtimestamp(since_val_epoch).strftime('%Y-%m-%d %H:%M:%S')
        logger.debug('Fetching: {}, TF: {}, Since: {}, Limit: {}'.format(symbol, timeframe, since_dt, limit))
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit, params=params)

    @retry
    def fetch_order(self, oid, symbol):
        return self.exchange.fetch_order(oid, symbol)

    @retry
    def fetch_open_orders(self):
        return self.exchange.fetchOpenOrders()

    @retry
    def private_end_point(self, type, endpoint, params):
        '''
        Open method to allow calls to be made to any private end point.
        See here: https://github.com/backtrader/backtrader/wiki/Manual#implicit-api-methods

        - type: String, 'Get', 'Post','Put' or 'Delete'.
        - endpoint = String containing the endpoint address eg. 'order/{id}/cancel'
        - Params: Dict: An implicit method takes a dictionary of parameters, sends
          the request to the exchange and returns an exchange-specific JSON
          result from the API as is, unparsed.

        To get a list of all available methods with an exchange instance,
        including implicit methods and unified methods you can simply do the
        following:

        logger.debug(dir(backtrader.hitbtc()))
        '''
        return getattr(self.exchange, endpoint)(params)
