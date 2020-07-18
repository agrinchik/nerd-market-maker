from enum import Enum
from market_maker.strategies.MM001_gridmarketmaker import MM001_GridMarketMakerStrategy
from market_maker.strategies.MM002_ordermaker import MM002_OrderMakerStrategy


class MMStrategy(object):
    c = None
    long_name = ""
    prefix_name = ""

    def __init__(self, cls, long_name):
        self.clazz = cls
        self.long_name = long_name


class MMStrategyEnum(Enum):
    MM001_GRID_MARKET_MAKER_STRATEGY_ID = MMStrategy(MM001_GridMarketMakerStrategy, "MM001_GridMarketMakerStrategy")
    MM002_ORDER_MAKER_STRATEGY_ID = MMStrategy(MM002_OrderMakerStrategy, "MM002_OrderMakerStrategy")

    @classmethod
    def get_strategy_enum_by_str(cls, strategy_str):
        for name, member in MMStrategyEnum.__members__.items():
            if member.value.long_name == strategy_str:
                return member