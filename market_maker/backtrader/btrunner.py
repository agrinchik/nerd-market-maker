import time
import backtrader as bt
import datetime as dt
from market_maker.backtrader.ccxtbt import CCXTStore, CCXTFeed
from market_maker.utils import log
from market_maker.settings import settings
from market_maker.backtrader.strategy.strategy_enum import BTStrategyEnum
from market_maker.backtrader.broker_mappings import BrokerMappings
from market_maker.db.db_manager import DatabaseManager
from market_maker.utils.log import log_info
from market_maker.utils.log import log_error
import traceback

OHLCV_BAR_LIMIT = 200
PREFETCH_BARS = 200

logger = log.setup_supervisor_custom_logger('root')


class BacktraderRunner(object):
    def __init__(self):
        self._strategy_enum = None
        self._strategy_params = None

    def get_broker_config(self, db_robot_settings):
        return {
            'apiKey': db_robot_settings.apikey,
            'secret': db_robot_settings.secret,
            'nonce': lambda: str(int(time.time() * 1000)),
        }

    def calc_history_start_date(self, timeframe):
        prefetch_num_minutes = PREFETCH_BARS * timeframe
        return dt.datetime.utcnow() - dt.timedelta(minutes=prefetch_num_minutes)

    def get_target_currency(self, symbol):
        return "BTC"  # TODO: Reimplement

    def get_reference_currency(self, symbol):
        return "USD"  # TODO: Reimplement

    def init_cerebro(self, cerebro):
        exchange = settings.EXCHANGE
        robot_id = DatabaseManager.get_robot_id_list(settings.NUMBER_OF_ROBOTS)[0]
        db_robot_settings = DatabaseManager.retrieve_robot_settings(exchange, robot_id)
        symbol = db_robot_settings.symbol

        broker_config = self.get_broker_config(db_robot_settings)
        target_currency = self.get_target_currency(symbol)
        reference_currency = self.get_reference_currency(symbol)
        store = CCXTStore(cerebro=cerebro, exchange=exchange, currency=target_currency, config=broker_config, retries=5, rate_limit_factor=settings.NUMBER_OF_ROBOTS)

        broker_mapping = BrokerMappings.get_broker_mapping(exchange)
        broker = store.getbroker(broker_mapping=broker_mapping)
        broker.setcommission(0)
        cerebro.setbroker(broker)

        timeframe0 = 1
        hist_start_date0 = self.calc_history_start_date(timeframe0)
        data0 = store.getdata(
            dataname='{}/{}'.format(target_currency, reference_currency),
            name='{}'.format(symbol),
            timeframe=bt.TimeFrame.Minutes,
            fromdate=hist_start_date0,
            compression=timeframe0,
            ohlcv_limit=OHLCV_BAR_LIMIT,
            fetch_ohlcv_params={'partial': 'true'},
            merge_partial_live_bars=True,
        )
        # Add the feed
        cerebro.adddata(data0)

        timeframe1 = 5
        hist_start_date1 = self.calc_history_start_date(timeframe1)
        data1 = store.getdata(
            dataname='{}/{}'.format(target_currency, reference_currency),
            name='{}'.format(symbol),
            timeframe=bt.TimeFrame.Minutes,
            fromdate=hist_start_date1,
            compression=timeframe1,
            ohlcv_limit=OHLCV_BAR_LIMIT,
            fetch_ohlcv_params={'partial': 'true'},
            merge_partial_live_bars=True,
        )
        # Add the feed
        cerebro.adddata(data1)

        timeframe2 = 60
        hist_start_date2 = self.calc_history_start_date(timeframe2)
        data2 = store.getdata(
            dataname='{}/{}'.format(target_currency, reference_currency),
            name='{}'.format(symbol),
            timeframe=bt.TimeFrame.Minutes,
            fromdate=hist_start_date2,
            compression=timeframe2,
            ohlcv_limit=OHLCV_BAR_LIMIT,
            fetch_ohlcv_params={'partial': 'true'},
            merge_partial_live_bars=True,
        )
        # Add the feed
        cerebro.adddata(data2)

        timeframe3 = 1
        hist_start_date3 = self.calc_history_start_date(timeframe3 * 24 * 60)
        data3 = store.getdata(
            dataname='{}/{}'.format(target_currency, reference_currency),
            name='{}'.format(symbol),
            timeframe=bt.TimeFrame.Days,
            fromdate=hist_start_date3,
            compression=timeframe3,
            ohlcv_limit=OHLCV_BAR_LIMIT,
            fetch_ohlcv_params={'partial': 'true'},
            merge_partial_live_bars=True,
        )
        # Add the feed
        cerebro.adddata(data3)

        self.add_filter(data0)

    def add_filter(self, data):
        # Add the filter for dynamic updates of defined indicators
        data.addfilter(PartialBarFilter)

    def init_strategy_params(self, strategy_enum):
        self._strategy_params = dict()

    def add_strategy(self, cerebro):
        strategy_class = self._strategy_enum.value.clazz
        cerebro.addstrategy(strategy_class, **self._strategy_params)

    def start(self):
        try:
            strategy = "MM001_MarketMonitorStrategy"
            self._strategy_enum = BTStrategyEnum.get_strategy_enum_by_str(strategy)
            self.init_strategy_params(self._strategy_enum)

            cerebro = bt.Cerebro(quicknotify=True)
            self.init_cerebro(cerebro)
            self.add_strategy(cerebro)

            cerebro.run()

        except Exception as e:
            log_error(logger, traceback.format_exc(limit=3, chain=False), True)
