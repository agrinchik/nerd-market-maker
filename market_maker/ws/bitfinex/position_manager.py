"""
Module used to house all of the functions/classes used to handle positions
"""

import logging
from market_maker.models.bitfinex import Position


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
        self.logger.info("confirm_position_update(): raw_ws_data={}".format(raw_ws_data))
        position = Position.from_raw_position(raw_ws_data[2])
        self.open_positions[position["symbol"]] = position
        self.logger.info("Position update: {}".format(position))
        self.bfxapi._emit('position_update', position)

    async def confirm_position_closed(self, raw_ws_data):
        self.logger.info("confirm_position_closed(): raw_ws_data={}".format(raw_ws_data))
        position = Position.from_raw_position(raw_ws_data[2])
        if position["symbol"] in self.open_positions:
            del self.open_positions[position["symbol"]]
        self.logger.info("Position closed: {}".format(position["symbol"]))
        self.bfxapi._emit('position_closed', position)

