"""
Module used to house all of the functions/classes used to handle positions
"""

import logging
from market_maker.models.bitfinex import Position, PositionStatus
from market_maker.utils.log import log_info
from market_maker.settings import settings
from market_maker.db.db_manager import DatabaseManager

TRADE_POSITION_STATUS_INCREASE = 0
TRADE_POSITION_STATUS_PARTIAL_CLOSE = 1
TRADE_POSITION_STATUS_FULL_CLOSE = 2


class PositionManager:

    def __init__(self, bfxapi, logLevel='INFO'):
        self.bfxapi = bfxapi
        self.open_positions = {}
        self.closed_positions = {}

        self.logger = logging.getLogger('root')

    def get_open_positions(self):
        return self.open_positions

    def get_closed_positions(self):
        return self.closed_positions

    async def build_from_position_snapshot(self, raw_ws_data):
        self.logger.debug("build_from_position_snapshot(): raw_ws_data={}".format(raw_ws_data))
        psData = raw_ws_data[2]
        self.open_positions = {}
        for raw_position in psData:
            position = Position.from_raw_position(raw_position)
            self.open_positions[position["symbol"]] = position
            self.logger.info("Position snapshot={}".format(position))
        self.bfxapi._emit('position_snapshot', self.get_open_positions())

    async def confirm_position_new(self, raw_ws_data):
        self.logger.debug("confirm_position_new(): raw_ws_data={}".format(raw_ws_data))
        position = Position.from_raw_position(raw_ws_data[2])
        self.open_positions[position["symbol"]] = position
        self.logger.info("Position new: {}".format(position))
        self.bfxapi._emit('position_new', position)

    async def confirm_position_update(self, raw_ws_data):
        self.logger.debug("confirm_position_update(): raw_ws_data={}".format(raw_ws_data))
        position = Position.from_raw_position(raw_ws_data[2])
        symbol = position["symbol"]
        self.process_position_execution(self.open_positions[symbol], position)
        self.open_positions[symbol] = position
        self.logger.debug("Position update: {}".format(position))
        self.bfxapi._emit('position_update', position)

    async def confirm_position_closed(self, raw_ws_data):
        self.logger.debug("confirm_position_closed(): raw_ws_data={}".format(raw_ws_data))
        position = Position.from_raw_position(raw_ws_data[2])
        symbol = position["symbol"]
        self.logger.info("Position closed: {}".format(symbol))
        self.process_position_execution(self.open_positions[symbol], position)
        if symbol and symbol in self.open_positions:
            del self.open_positions[symbol]
        self.bfxapi._emit('position_closed', position)

    def get_trade_position_status(self, update_position_status, curr_position_qty, update_position_qty, trade_side):
        self.logger.info("get_trade_position_status(): update_position_status={}, curr_position_qty={}, update_position_qty={}, trade_side={}".format(
            update_position_status, curr_position_qty, update_position_qty, trade_side))
        is_trade_long = True if trade_side == "Buy" else False
        if update_position_status == PositionStatus.CLOSED and update_position_qty == 0:
            return TRADE_POSITION_STATUS_FULL_CLOSE
        if curr_position_qty > 0 and is_trade_long or curr_position_qty < 0 and not is_trade_long:
            return TRADE_POSITION_STATUS_INCREASE
        if curr_position_qty > 0 and not is_trade_long or curr_position_qty < 0 and is_trade_long:
            return TRADE_POSITION_STATUS_PARTIAL_CLOSE

    def process_position_execution(self, curr_position, update_position):
        # Log position execution
        update_position_status = Position.get_position_status(update_position)
        curr_position_qty = curr_position['currentQty']
        update_position_qty = update_position['currentQty']
        if update_position_status == PositionStatus.ACTIVE and curr_position_qty == update_position_qty:
            self.logger.debug("Position quantity did not change - return")
            return

        upd_position_trade_info = Position.get_position_trade_info(update_position)
        trade_side = upd_position_trade_info.get_trade_side_str()
        trade_price = upd_position_trade_info.trade_price
        trade_size = upd_position_trade_info.trade_amount
        symbol = update_position['symbol']
        trade_position_status = self.get_trade_position_status(update_position_status, curr_position_qty, update_position_qty, trade_side)
        if trade_position_status == TRADE_POSITION_STATUS_INCREASE:
            log_info(self.logger, "Execution (position increase): {} {} quantity of {} at {}".format(trade_side, trade_size, symbol, trade_price), True)
        elif trade_position_status == TRADE_POSITION_STATUS_PARTIAL_CLOSE:
            log_info(self.logger, "Execution (position partial close): {} {} quantity of {} at {}".format(trade_side, trade_size, symbol, trade_price), True)
        elif trade_position_status == TRADE_POSITION_STATUS_FULL_CLOSE:
            log_info(self.logger, "Execution (position fully closed): {} {} quantity of {} at {}".format(trade_side, trade_size, symbol, trade_price), True)
            last_position_qty = curr_position_qty
