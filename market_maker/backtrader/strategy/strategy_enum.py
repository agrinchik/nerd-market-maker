from enum import Enum
from market_maker.backtrader.strategy.MM001_marketmonitor import MM001_MarketMonitorStrategy


class BTStrategy(object):
    c = None
    long_name = ""
    prefix_name = ""

    def __init__(self, cls, long_name):
        self.clazz = cls
        self.long_name = long_name


class BTStrategyEnum(Enum):
    MM001_MARKET_MONITOR_STRATEGY_ID = BTStrategy(MM001_MarketMonitorStrategy, "MM001_MarketMonitorStrategy")

    @classmethod
    def get_strategy_enum_by_str(cls, strategy_str):
        for name, member in BTStrategyEnum.__members__.items():
            if member.value.long_name == strategy_str:
                return member
