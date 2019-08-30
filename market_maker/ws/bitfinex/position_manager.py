"""
Module used to house all of the functions/classes used to handle positions
"""

from market_maker.utils.bitfinex.custom_logger import CustomLogger
from market_maker.models.bitfinex import Position


class PositionManager:

    def __init__(self, bfxapi, logLevel='INFO'):
        self.bfxapi = bfxapi
        self.open_positions = {}
        self.closed_positions = {}

        self.logger = CustomLogger('BfxPositionManager', logLevel=logLevel)

    def get_open_positions(self):
        return list(self.open_positions.values())

    def get_closed_positions(self):
        return list(self.closed_positions.values())

    async def build_from_position_snapshot(self, raw_ws_data):
        psData = raw_ws_data[2]
        self.open_positions = {}
        for raw_position in psData:
            position = Position.from_raw_position(raw_position)
            self.open_positions[position.id] = position
            self.logger.info("Position={}".format(position))
        self.logger.info("Position snapshot: {}".format(raw_ws_data))
        self.bfxapi._emit('position_snapshot', self.get_open_positions())

    async def confirm_position_new(self, raw_ws_data):
        position = Position.from_raw_position(raw_ws_data[2])
        self.open_positions[position.id] = position
        self.logger.info("Position new: {}".format(position))
        self.bfxapi._emit('position_new', position)

    async def confirm_position_update(self, raw_ws_data):
        position = Position.from_raw_position(raw_ws_data[2])
        self.open_positions[position.id] = position
        self.logger.info("Position update: {}".format(position))
        self.bfxapi._emit('position_update', position)

    async def confirm_position_closed(self, raw_ws_data):
        position = Position.from_raw_position(raw_ws_data[2])
        if position.id in self.open_positions:
            del self.open_positions[position.id]
        self.logger.info("Position closed: {} {}".format(position.symbol, position.status))
        self.bfxapi._emit('position_closed', position)

