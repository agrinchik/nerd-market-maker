from enum import Enum
from market_maker.backtrader.strategy.btmarketsnapshot import BTMarketSnapshotStrategy


class BTStrategy(object):
    c = None
    long_name = ""
    prefix_name = ""

    def __init__(self, cls, long_name):
        self.clazz = cls
        self.long_name = long_name


class BTStrategyEnum(Enum):
    BT_MARKET_SNAPSHOT_STRATEGY_ID = BTStrategy(BTMarketSnapshotStrategy, "BTMarketSnapshotStrategy")

    @classmethod
    def get_strategy_enum_by_str(cls, strategy_str):
        for name, member in BTStrategyEnum.__members__.items():
            if member.value.long_name == strategy_str:
                return member
