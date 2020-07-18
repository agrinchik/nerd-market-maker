from market_maker.strategies.config.strategy_enum import MMStrategyEnum
from market_maker.strategies.MM001_gridmarketmaker import MM001_GridMarketMakerStrategy
from market_maker.strategies.MM002_ordermaker import MM002_OrderMakerStrategy


class StrategyFactory(object):
    @classmethod
    def build_strategy(cls, strategy_str, logger, exchange):
        strategy_enum = MMStrategyEnum.get_strategy_enum_by_str(strategy_str)
        if strategy_enum == MMStrategyEnum.MM001_GRID_MARKET_MAKER_STRATEGY_ID:
            return MM001_GridMarketMakerStrategy(logger, exchange)
        elif strategy_enum == MMStrategyEnum.MM002_ORDER_MAKER_STRATEGY_ID:
            return MM002_OrderMakerStrategy(logger, exchange)
        else:
            raise Exception("StrategyFactory.build_strategy_processor(): Configuration exception")