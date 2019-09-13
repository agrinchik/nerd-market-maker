"""
Module used to house all of the functions/classes used to handle orders
"""

import time
import asyncio
import logging

from market_maker.models.bitfinex import Order


class OrderManager:
    """
    Handles all of the functionality for opening, updating and closing order.
    Also contains state such as all of your open orders and orders that have
    closed.
    """

    def __init__(self, bfxapi, logLevel='INFO'):
        self.bfxapi = bfxapi
        self.pending_orders = {}
        self.open_orders = {}

        self.logger = logging.getLogger('root')

    def get_open_orders(self):
        return list(self.open_orders.values())

    def get_pending_orders(self):
        return list(self.pending_orders.values())

    async def build_from_order_snapshot(self, raw_ws_data):
        '''
        Rebuild the user orderbook based on an incoming snapshot
        '''
        osData = raw_ws_data[2]
        self.open_orders = {}
        for raw_order in osData:
            order = Order.from_raw_order(raw_order)
            self.open_orders[order["orderID"]] = order
        self.bfxapi._emit('order_snapshot', self.get_open_orders())

    async def confirm_order_new(self, raw_ws_data):
        order = Order.from_raw_order(raw_ws_data[2])
        self.open_orders[order["orderID"]] = order
        self.bfxapi._emit('order_confirmed', order)
        self.logger.info("Order new: {}".format(order))
        self.bfxapi._emit('order_new', order)

    async def confirm_order_update(self, raw_ws_data):
        order = Order.from_raw_order(raw_ws_data[2])
        self.open_orders[order["orderID"]] = order
        self.logger.info("Order update: {}".format(order))
        self.bfxapi._emit('order_update', order)

    async def confirm_order_closed(self, raw_ws_data):
        order = Order.from_raw_order(raw_ws_data[2])
        if order["orderID"] in self.open_orders:
            del self.open_orders[order["orderID"]]
        self.bfxapi._emit('order_confirmed', order)
        self.logger.info("Order closed: {} {} {}".format(order["orderID"], order["symbol"], order["ordStatus"]))
        self.bfxapi._emit('order_closed', order)


