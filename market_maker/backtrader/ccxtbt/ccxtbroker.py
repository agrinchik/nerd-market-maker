#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015, 2016, 2017 Daniel Rodriguez
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

import collections
import json
from market_maker.utils import log

from backtrader import BrokerBase, OrderBase, Order
from backtrader.position import Position
from backtrader.utils.py3 import queue, with_metaclass
from market_maker.backtrader.utils import UTC_to_CurrTZ

from .ccxtstore import CCXTStore

logger = log.setup_supervisor_custom_logger('root')


class CCXTOrder(OrderBase):
    def __init__(self, owner, data, ccxt_order):
        self.owner = owner
        self.data = data
        self.ccxt_order = ccxt_order
        self.ordtype = self.Buy if ccxt_order['side'] == 'buy' else self.Sell
        self.size = float(ccxt_order['amount'])

        super(CCXTOrder, self).__init__()


class MetaCCXTBroker(BrokerBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaCCXTBroker, cls).__init__(name, bases, dct)
        CCXTStore.BrokerCls = cls


class CCXTBroker(with_metaclass(MetaCCXTBroker, BrokerBase)):
    '''Broker implementation for CCXT cryptocurrency trading library.
    This class maps the orders/positions from CCXT to the
    internal API of ``backtrader``.

    Broker mapping added as I noticed that there differences between the expected
    order_types and retuned status's from canceling an order

    Added a new mappings parameter to the script with defaults.

    Added a get_balance function. Manually check the account balance and update brokers
    self.cash and self.value. This helps alleviate rate limit issues.

    Added a new get_wallet_balance method. This will allow manual checking of the any coins
        The method will allow setting parameters. Useful for dealing with multiple assets

    Modified getcash() and getvalue():
        Backtrader will call getcash and getvalue before and after next, slowing things down
        with rest calls. As such, th

    The broker mapping should contain a new dict for order_types and mappings like below:

    broker_mapping = {
        'order_types': {
            bt.Order.Market: 'market',
            bt.Order.Limit: 'limit',
            bt.Order.Stop: 'stop-loss', #stop-loss for kraken, stop for bitmex
            bt.Order.StopLimit: 'stop limit'
        },
        'mappings':{
            'closed_order':{
                'key': 'status',
                'value':'closed'
                },
            'canceled_order':{
                'key': 'result',
                'value':1}
                }
        }

    Added new private_end_point method to allow using any private non-unified end point

    '''

    order_types = {Order.Market: 'market',
                   Order.Limit: 'limit',
                   Order.Stop: 'stop',  # stop-loss for kraken, stop for bitmex
                   Order.StopLimit: 'stop limit'}

    mappings = {
        'closed_order': {
            'key': 'status',
            'value': 'closed'
        },
        'canceled_order': {
            'key': 'status',
            'value': 'canceled'}
    }

    def __init__(self, broker_mapping=None, **kwargs):
        super(CCXTBroker, self).__init__()

        if broker_mapping is not None:
            try:
                self.order_types = broker_mapping['order_types']
            except KeyError:  # Might not want to change the order types
                pass
            try:
                self.mappings = broker_mapping['mappings']
            except KeyError:  # might not want to change the mappings
                pass

        self.store = CCXTStore(**kwargs)

        self.currency = self.store.currency

        self.positions = collections.defaultdict(Position)

        self.indent = 4  # For pretty printing dictionaries

        self.notifs = queue.Queue()  # holds orders which are notified

        self.open_orders = list()

        self.startingcash = self.store._cash
        self.startingvalue = self.store._value

    def fetch_ticker(self, currency, params={}):
        ticker_data = self.store.fetch_ticker(currency, params=params)
        return ticker_data

    def get_balance(self):
        balance = self.store.get_balance()
        self.cash = self.store._cash
        self.value = self.store._value
        return self.cash, self.value

    def get_wallet_balance(self, currency, params={}):
        balance = self.store.get_wallet_balance(currency, params=params)
        cash = balance['free'][currency]
        value = balance['total'][currency]
        return cash, value

    def getcash(self):
        # Get cash seems to always be called before get value
        # Therefore it makes sense to add getbalance here.
        # return self.store.getcash(self.currency)
        self.cash = self.store._cash
        return self.cash

    def getvalue(self, datas=None):
        # return self.store.getvalue(self.currency)
        self.value = self.store._value
        return self.value

    def get_notification(self):
        try:
            return self.notifs.get(False)
        except queue.Empty:
            return None

    def notify(self, order):
        self.notifs.put(order.clone())

    def getposition(self, data, clone=True):
        # return self.o.getposition(data._dataname, clone=clone)
        pos = self.positions[data._dataname]
        if clone:
            pos = pos.clone()
        return pos

    def log_datas(self):
        combined_msg = "next() - Datas:\n"
        strategy = self.cerebro.runningstrats[0]
        datas = strategy.datas
        for i, data in enumerate(datas):
            combined_msg += "TF{}: len(data{})={}\n".format(i, i, len(data))
            if len(data.datetime) > 1:
                combined_msg += "data{}.datetime[-1] = {}, ".format(i, UTC_to_CurrTZ(data.datetime.datetime(-1)))
                combined_msg += "data{}.open[-1]={}, ".format(i, data.open[-1])
                combined_msg += "data{}.high[-1]={}, ".format(i, data.high[-1])
                combined_msg += "data{}.low[-1]={}, ".format(i, data.low[-1])
                combined_msg += "data{}.close[-1]={}, ".format(i, data.close[-1])
                combined_msg += "data{}.volume[-1]={}\n".format(i, data.volume[-1])
            combined_msg += "data{}.datetime[0]  = {}, ".format(i, UTC_to_CurrTZ(data.datetime.datetime(0)))
            combined_msg += "data{}.open[0]={}, ".format(i, data.open[0])
            combined_msg += "data{}.high[0]={}, ".format(i, data.high[0])
            combined_msg += "data{}.low[0]={}, ".format(i, data.low[0])
            combined_msg += "data{}.close[0]={}, ".format(i, data.close[0])
            combined_msg += "data{}.volume[0]={}\n".format(i, data.volume[0])
        combined_msg += 'Indicators:\n'
        combined_msg += 'strategy.atr_data0 = {}\n'.format(strategy.atr_data0[0] if len(strategy.atr_data0) > 0 else 'N/A')
        combined_msg += 'strategy.sma_data0 = {}\n'.format(strategy.sma_data0[0] if len(strategy.sma_data0) > 0 else 'N/A')
        combined_msg += 'strategy.atr_data0_pct = {}%\n'.format(round(strategy.atr_data0_pct[0], 2) if len(strategy.atr_data0_pct) > 0 else 'N/A')
        combined_msg += 'strategy.atr_data1 = {}\n'.format(strategy.atr_data1[0] if len(strategy.atr_data1) > 0 else 'N/A')
        combined_msg += 'strategy.sma_data1 = {}\n'.format(strategy.sma_data1[0] if len(strategy.sma_data1) > 0 else 'N/A')
        combined_msg += 'strategy.atr_data1_pct = {}%\n'.format(round(strategy.atr_data1_pct[0], 2) if len(strategy.atr_data1_pct) > 0 else 'N/A')
        combined_msg += 'strategy.atr_data2 = {}\n'.format(strategy.atr_data2[0] if len(strategy.atr_data2) > 0 else 'N/A')
        combined_msg += 'strategy.sma_data2 = {}\n'.format(strategy.sma_data2[0] if len(strategy.sma_data2) > 0 else 'N/A')
        combined_msg += 'strategy.atr_data2_pct = {}%\n'.format(round(strategy.atr_data2_pct[0], 2) if len(strategy.atr_data2_pct) > 0 else 'N/A')
        combined_msg += 'strategy.atr_data3 = {}\n'.format(strategy.atr_data3[0] if len(strategy.atr_data3) > 0 else 'N/A')
        combined_msg += 'strategy.sma_data3 = {}\n'.format(strategy.sma_data3[0] if len(strategy.sma_data3) > 0 else 'N/A')
        combined_msg += 'strategy.atr_data3_pct = {}%\n'.format(round(strategy.atr_data3_pct[0], 2) if len(strategy.atr_data3_pct) > 0 else 'N/A')
        logger.debug(combined_msg)

    def next(self):
        logger.debug('Broker next() called')
        self.log_datas()

        for o_order in list(self.open_orders):
            oID = o_order.ccxt_order['id']

            # Print debug before fetching so we know which order is giving an
            # issue if it crashes
            logger.debug('Fetching Order ID: {}'.format(oID))

            # Get the order
            ccxt_order = self.store.fetch_order(oID, o_order.data.symbol)

            logger.debug(json.dumps(ccxt_order, indent=self.indent))

            # Check if the order is closed
            if ccxt_order[self.mappings['closed_order']['key']] == self.mappings['closed_order']['value']:
                data = o_order.data
                pos = self.getposition(data, clone=False)
                size = ccxt_order['amount']
                price = ccxt_order['price']
                if ccxt_order['side'] == 'sell':
                    size = -size
                psize, pprice, opened, closed = pos.update(size, price)

                # comminfo = self.getcommissioninfo(data)
                closedvalue = closedcomm = 0.0
                openedvalue = openedcomm = 0.0
                margin = pnl = 0.0

                o_order.execute(data.datetime[0], size, price, closed, closedvalue, closedcomm, opened, openedvalue, openedcomm, margin, pnl, psize, pprice)

                ######## TODO: Review later ##########
                #if o_order.executed.remsize:
                #    order.partial()
                #    self.notify(order)
                #else:
                #   order.completed()
                #    self.notify(order)
                ######################################
                o_order.completed()
                self.notify(o_order)
                self.open_orders.remove(o_order)


    def _submit(self, owner, data, exectype, side, amount, price, params):
        order_type = self.order_types.get(exectype) if exectype else 'market'

        # Extract CCXT specific params if passed to the order
        params = params['params'] if 'params' in params else params

        ret_ord = self.store.create_order(symbol=data.symbol, order_type=order_type, side=side,
                                          amount=amount, price=price, params=params)

        _order = self.store.fetch_order(ret_ord['id'], data.symbol)

        order = CCXTOrder(owner, data, _order)
        order.addcomminfo(self.getcommissioninfo(data))
        self.open_orders.append(order)

        #TODO: Check if needed!
        self.notify(order)
        return order

    def buy(self, owner, data, size, price=None, plimit=None,
            exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None,
            **kwargs):
        del kwargs['parent']
        del kwargs['transmit']
        return self._submit(owner, data, exectype, 'buy', size, price, kwargs)

    def sell(self, owner, data, size, price=None, plimit=None,
             exectype=None, valid=None, tradeid=0, oco=None,
             trailamount=None, trailpercent=None,
             **kwargs):
        del kwargs['parent']
        del kwargs['transmit']
        return self._submit(owner, data, exectype, 'sell', size, price, kwargs)

    def cancel(self, order):

        oID = order.ccxt_order['id']

        logger.debug('Broker cancel() called')
        logger.debug('Fetching Order ID: {}'.format(oID))

        # check first if the order has already been filled otherwise an error
        # might be raised if we try to cancel an order that is not open.
        ccxt_order = self.store.fetch_order(oID, order.data.symbol)

        logger.debug(json.dumps(ccxt_order, indent=self.indent))

        if ccxt_order[self.mappings['closed_order']['key']] == self.mappings['closed_order']['value']:
            return order

        self.store.cancel_order(oID, order.data.symbol)

        # check if the order has been actually cancelled
        ccxt_order = self.store.fetch_order(oID, order.data.symbol)

        logger.debug(json.dumps(ccxt_order, indent=self.indent))
        logger.debug('Value Received: {}'.format(ccxt_order[self.mappings['canceled_order']['key']]))
        logger.debug('Value Expected: {}'.format(self.mappings['canceled_order']['value']))

        if ccxt_order[self.mappings['canceled_order']['key']] == self.mappings['canceled_order']['value']:
            self.open_orders.remove(order)
            order.cancel()
            self.notify(order)
        return order

    def get_orders_open(self, safe=False):
        return self.store.fetch_open_orders()

    def fetch_my_trades(self, symbol, since, limit, params={}):
        return self.store.fetch_my_trades(symbol, since, limit, params)

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
        endpoint_str = endpoint.replace('/', '_')
        endpoint_str = endpoint_str.replace('{', '')
        endpoint_str = endpoint_str.replace('}', '')

        method_str = 'private_' + type.lower() + endpoint_str.lower()

        return self.store.private_end_point(type=type, endpoint=method_str, params=params)
