"""
Module used to house all of the functions/classes used to handle orders
"""

import logging

from market_maker.models.bitfinex import Order, OrderStatus
from market_maker.utils.log import log_info

ORDER_CLOSE_POSITION_STATUS_INCREASE = 0
ORDER_CLOSE_POSITION_STATUS_PARTIAL_CLOSE = 1
ORDER_CLOSE_POSITION_STATUS_FULL_CLOSE = 2

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
        self.logger.info("confirm_order_new(): raw_ws_data={}".format(raw_ws_data))
        order = Order.from_raw_order(raw_ws_data[2])
        self.open_orders[order["orderID"]] = order
        self.bfxapi._emit('order_confirmed', order)
        self.logger.info("Order new: {}".format(order))
        self.bfxapi._emit('order_new', order)

    async def confirm_order_update(self, raw_ws_data):
        self.logger.info("confirm_order_update(): raw_ws_data={}".format(raw_ws_data))
        order = Order.from_raw_order(raw_ws_data[2])
        orderId = order["orderID"]
        self.log_order_execution(self.open_orders[orderId], order)
        self.open_orders[orderId] = order
        self.logger.info("Order update: {}".format(order))
        self.bfxapi._emit('order_update', order)

    async def confirm_order_closed(self, raw_ws_data):
        self.logger.info("confirm_order_closed(): raw_ws_data={}".format(raw_ws_data))
        order = Order.from_raw_order(raw_ws_data[2])
        orderId = order["orderID"]
        if orderId in self.open_orders:
            self.log_order_execution(self.open_orders[orderId], order)
            del self.open_orders[orderId]
            self.bfxapi._emit('order_confirmed', order)
            self.logger.info("Order closed: {}".format(order))
            self.bfxapi._emit('order_closed', order)

    def get_current_position(self):
        return self.bfxapi.positionManager.get_open_positions().get(self.bfxapi.symbol)

    def get_order_close_position_status(self, position_qty, order_side, order_price):
        self.logger.info("get_order_close_position_status(): curr_position={}, order_side={}, order_price={}".format(position_qty, order_side, order_price))
        is_order_long = True if order_side == "Buy" else False
        order_price_with_sign = order_price if is_order_long is True else -order_price
        if position_qty == 0 or position_qty == -order_price_with_sign:
            return ORDER_CLOSE_POSITION_STATUS_FULL_CLOSE
        if position_qty > 0 and order_price_with_sign > 0 or position_qty < 0 and order_price_with_sign < 0:
            return ORDER_CLOSE_POSITION_STATUS_INCREASE
        if position_qty > 0 and order_price_with_sign < 0 or position_qty < 0 and order_price_with_sign > 0:
            return ORDER_CLOSE_POSITION_STATUS_PARTIAL_CLOSE

    def log_order_execution(self, order, update_order):
        # Log order execution
        order_status = Order.get_order_status(update_order)
        is_canceled = order_status == OrderStatus.CANCELED
        if is_canceled is False:
            curr_position = self.get_current_position()
            position_qty = curr_position['currentQty'] if curr_position is not None else 0
            contExecuted = update_order['cumQty'] - order['cumQty']
            order_side = update_order['side']
            order_price = update_order['price']
            symbol = update_order['symbol']
            order_close_position_status = self.get_order_close_position_status(position_qty, order_side, order_price)
            if order_close_position_status == ORDER_CLOSE_POSITION_STATUS_INCREASE:
                log_info(self.logger, "Execution (position increase): {} {} contracts of {} at {}".format(order_side, contExecuted, symbol, order_price), True)
            elif order_close_position_status == ORDER_CLOSE_POSITION_STATUS_PARTIAL_CLOSE:
                log_info(self.logger, "Execution (position partial close): {} {} contracts of {} at {}".format(order_side, contExecuted, symbol, order_price), True)
            elif order_close_position_status == ORDER_CLOSE_POSITION_STATUS_FULL_CLOSE:
                log_info(self.logger, "Execution (position fully closed): {} {} contracts of {} at {}".format(order_side, contExecuted, symbol, order_price), True)


