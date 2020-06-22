from enum import Enum
from market_maker.backtrader.strategy.MM001_marketsnapshot import MM001_MarketSnapshotStrategy


class BTStrategy(object):
    c = None
    long_name = ""
    prefix_name = ""

    def __init__(self, cls, long_name):
        self.clazz = cls
        self.long_name = long_name


class BTStrategyEnum(Enum):
    MM001_MARKET_SNAPSHOT_STRATEGY_ID = BTStrategy(MM001_MarketSnapshotStrategy, "MM001_MarketSnapshotStrategy")

    @classmethod
    def get_strategy_enum_by_str(cls, strategy_str):
        for name, member in BTStrategyEnum.__members__.items():
            if member.value.long_name == strategy_str:
                return member
