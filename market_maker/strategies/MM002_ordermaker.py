
from market_maker.strategies.genericstrategy import GenericStrategy
from datetime import datetime


class MM002_OrderMakerStrategy(GenericStrategy):

    def __init__(self, logger, exchange):
        super().__init__(logger, exchange)
        self.curr_market_snapshot = None
        self.is_trading_suspended = False
        self.price_change_last_check = datetime.now()
        self.price_change_last_price = -1

    def on_market_snapshot_update(self):
        pass