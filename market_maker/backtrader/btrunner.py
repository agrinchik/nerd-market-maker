import time
import backtrader as bt
import datetime as dt
from market_maker.backtrader.ccxtbt import CCXTStore
from market_maker.utils import log
from market_maker.settings import settings
from market_maker.backtrader.strategy.strategy_enum import BTStrategyEnum
from market_maker.backtrader.broker_mappings import BrokerMappings
from market_maker.db.db_manager import DatabaseManager
from market_maker.utils.log import log_error
import traceback

OHLCV_BAR_LIMIT = 100
PREFETCH_BARS = 100

logger = log.setup_supervisor_custom_logger('root')


class BacktraderRunner(object):
    def __init__(self):
        self._cerebro = None
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
        is_sandbox_mode = True if settings.ENV == "test" else False
        store = CCXTStore(cerebro=cerebro, exchange=exchange, currency=target_currency, config=broker_config, retries=5, rate_limit_factor=settings.NUMBER_OF_ROBOTS, sandbox=is_sandbox_mode)

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
            fetch_ohlcv_params={'partial': 'false'},
            merge_partial_live_bars=False,
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
            fetch_ohlcv_params={'partial': 'false'},
            merge_partial_live_bars=False,
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
            fetch_ohlcv_params={'partial': 'false'},
            merge_partial_live_bars=False,
        )
        # Add the feed
        cerebro.adddata(data3)

    def init_strategy_params(self, strategy_enum):
        self._strategy_params = dict()

    def add_strategy(self, cerebro):
        strategy_class = self._strategy_enum.value.clazz
        cerebro.addstrategy(strategy_class, **self._strategy_params)

    def get_market_snapshot(self):
        strategy = self._cerebro.runningstrats[0] if len(self._cerebro.strats) > 0 and len(self._cerebro.runningstrats) > 0 else None
        if strategy is not None and strategy.is_datas_live() and strategy.is_live_status() and strategy.is_all_datas_live_state():
            return strategy.get_market_snapshot()
        else:
            return None

    def start(self):
        try:
            self._strategy_enum = BTStrategyEnum.MM001_MARKET_SNAPSHOT_STRATEGY_ID
            self.init_strategy_params(self._strategy_enum)

            self._cerebro = bt.Cerebro(quicknotify=True)
            self.init_cerebro(self._cerebro)
            self.add_strategy(self._cerebro)

            self._cerebro.run()

        except Exception as e:
            log_error(logger, traceback.format_exc(limit=3, chain=False), True)
