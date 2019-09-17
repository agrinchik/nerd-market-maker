"""
Module used to house all of the functions/classes used to handle orders
"""

import logging

from market_maker.models.bitfinex import Order, OrderStatus
from market_maker.utils.log import log_info


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

    def get_current_position(self):
        return self.bfxapi.positionManager.get_open_positions().get(self.bfxapi.symbol)

    def is_position_partial_close(self, curr_position, order_side):
        is_order_long = True if order_side == "Buy" else False
        if curr_position == 0 or curr_position > 0 and is_order_long is True or curr_position < 0 and is_order_long is False:
            return False
        else:
            return True

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

    def log_order_execution(self, order, update_order):
        # Log order execution
        order_status = Order.get_order_status(update_order)
        is_canceled = order_status == OrderStatus.CANCELED
        if not is_canceled:
            curr_position = self.get_current_position()['currentQty']
            is_position_partial_close = self.is_position_partial_close(curr_position, order['side'])
            contExecuted = update_order['cumQty'] - order['cumQty']
            if curr_position != 0:
                if is_position_partial_close is False:
                    log_info(self.logger, "Execution (position increase): {} {} contracts of {} at {}".format(order['side'], contExecuted, order['symbol'], order['price']), True)
                else:
                    log_info(self.logger, "Execution (position partial close): {} {} contracts of {} at {}".format(order['side'], contExecuted, order['symbol'], order['price']), True)
            else:
                log_info(self.logger, "Execution (position fully closed): {} {} contracts of {} at {}".format(order['side'], contExecuted, order['symbol'], order['price']), True)


