"""
Module used to house all of the functions/classes used to handle orders
"""

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
        self.open_orders = {}

        self.logger = logging.getLogger('root')

    def get_open_orders(self):
        return list(self.open_orders.values())

    def add_new_multiple_orders_rest_apiv1(self, raw_rest_data):
        for raw_order in raw_rest_data:
            order = Order.from_raw_order_api_v1(raw_order)
            self.open_orders[order["orderID"]] = order
        self.logger.debug("open_orders: {}".format(self.get_open_orders()))

    async def build_from_order_snapshot(self, raw_ws_data):
        '''
        Rebuild the user orderbook based on an incoming snapshot
        '''
        osData = raw_ws_data[2]
        self.open_orders = {}
        for raw_order in osData:
            order = Order.from_raw_order_api_v2(raw_order)
            self.open_orders[order["orderID"]] = order
        self.bfxapi._emit('order_snapshot', self.get_open_orders())
        self.logger.debug("open_orders: {}".format(self.get_open_orders()))

    async def confirm_order_new(self, raw_ws_data):
        self.logger.debug("confirm_order_new(): raw_ws_data={}".format(raw_ws_data))
        order = Order.from_raw_order_api_v2(raw_ws_data[2])
        self.open_orders[order["orderID"]] = order
        self.bfxapi._emit('order_confirmed', order)
        self.logger.info("Order new: {}".format(order))
        self.logger.debug("open_orders: {}".format(self.get_open_orders()))
        self.bfxapi._emit('order_new', order)

    async def confirm_order_update(self, raw_ws_data):
        self.logger.debug("confirm_order_update(): raw_ws_data={}".format(raw_ws_data))
        order = Order.from_raw_order_api_v2(raw_ws_data[2])
        orderId = order["orderID"]
        self.open_orders[orderId] = order
        self.logger.debug("Order update: {}".format(order))
        self.logger.debug("open_orders: {}".format(self.get_open_orders()))
        self.bfxapi._emit('order_update', order)

    async def confirm_order_closed(self, raw_ws_data):
        self.logger.debug("confirm_order_closed(): raw_ws_data={}".format(raw_ws_data))
        order = Order.from_raw_order_api_v2(raw_ws_data[2])
        orderId = order["orderID"]
        if orderId in self.open_orders:
            del self.open_orders[orderId]
            self.bfxapi._emit('order_confirmed', order)
            self.logger.info("Order closed: {}".format(order))
            self.logger.debug("open_orders: {}".format(self.get_open_orders()))
            self.bfxapi._emit('order_closed', order)

    def get_current_position(self):
        return self.bfxapi.positionManager.get_open_positions().get(self.bfxapi.symbol)





