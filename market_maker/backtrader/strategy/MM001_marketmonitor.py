import backtrader as bt
import backtrader.indicators as btind
from market_maker.utils import log
from market_maker.backtrader.utils import UTC_to_CurrTZ

logger = log.setup_supervisor_custom_logger('root')


class MM001_MarketMonitorStrategy(bt.Strategy):
    params = (
        ("debug", False),
    )

    def __init__(self):
        self.status = None
        self.atr_data0 = btind.AverageTrueRange(self.data0, period=14, movav=btind.MovAv.SMA)
        self.sma_data0 = btind.SimpleMovingAverage(self.data0.close, period=14)
        self.atr_data0_pct = (self.atr_data0 / self.sma_data0) * 100

        self.atr_data1 = btind.AverageTrueRange(self.data1, period=14, movav=btind.MovAv.SMA)
        self.sma_data1 = btind.SimpleMovingAverage(self.data1.close, period=14)
        self.atr_data1_pct = (self.atr_data1 / self.sma_data1) * 100

        self.atr_data2 = btind.AverageTrueRange(self.data2, period=14, movav=btind.MovAv.SMA)
        self.sma_data2 = btind.SimpleMovingAverage(self.data2.close, period=14)
        self.atr_data2_pct = (self.atr_data2 / self.sma_data2) * 100

        self.atr_data3 = btind.AverageTrueRange(self.data3, period=14, movav=btind.MovAv.SMA)
        self.sma_data3 = btind.SimpleMovingAverage(self.data3.close, period=14)
        self.atr_data3_pct = (self.atr_data3 / self.sma_data3) * 100

    def get_updateable_indicators_map(self):
        data1 = self.data1
        data2 = self.data2
        data3 = self.data3
        return {data1: [self.atr_data1, self.sma_data1, self.atr_data1_pct],
                data2: [self.atr_data2, self.sma_data2, self.atr_data2_pct],
                data3: [self.atr_data3, self.sma_data3, self.atr_data3_pct]}

    def islivedata(self):
        return self.data.islive()

    def notify_data(self, data, status, *args, **kwargs):
        self.status = self.data._getstatusname(status)
        logger.info("notify_data() - status={}".format(self.status))
        if status == data.LIVE:
            logger.info("**** Initialized the Backtrader in LIVE mode: {} ****".format(self.data.symbol))
            logger.info("=" * 120)
            logger.info("LIVE DATA - MM001_MarketMonitorStrategy initialized")
            logger.info("=" * 120)

    def next(self):
        try:
            logger.info("len(self.datas)={}".format(len(self.datas)))
            logger.info("len(self.data0)={}".format(len(self.data0)))
            logger.info("len(self.data1)={}".format(len(self.data1)))
            logger.info("len(self.data2)={}".format(len(self.data2)))
            logger.info("len(self.data3)={}".format(len(self.data3)))
            if self.islivedata():
                logger.info("BEGIN next(): status={}".format(self.status))

            if self.islivedata() and self.status != "LIVE":
                logger.info("%s - %.8f" % (self.status, self.data0.close[0]))
                return

            self.print_all_debug_info()
        except Exception as e:
            self.broker.cerebro.runstop()
            raise e

    def log_data(self, idx, data):
        logger.info('self.data{}.datetime[0] = {}'.format(idx, UTC_to_CurrTZ(data.datetime.datetime(0))))
        logger.info('self.data{}.open[0] = {}'.format(idx, data.open[0]))
        logger.info('self.data{}.high[0] = {}'.format(idx, data.high[0]))
        logger.info('self.data{}.low[0] = {}'.format(idx, data.low[0]))
        logger.info('self.data{}.close[0] = {}'.format(idx, data.close[0]))
        logger.info('self.data{}.volume[0] = {}'.format(idx, data.volume[0]))

    def log_indicators(self, idx, atr, sma, atr_pct):
        logger.info('self.sma_data{} = {}'.format(idx, sma))
        logger.info('self.atr_data{} = {}'.format(idx, atr))
        logger.info('self.atr_data{}_pct = {}%'.format(idx, round(atr_pct, 2)))

    def print_all_debug_info(self):
        logger.info('---------------------- INSIDE NEXT DEBUG --------------------------')
        self.log_data(0, self.data0)
        self.log_data(1, self.data1)
        self.log_data(2, self.data2)
        self.log_data(3, self.data3)

        self.log_indicators(0, self.atr_data0[0], self.sma_data0[0], self.atr_data0_pct[0])
        self.log_indicators(1, self.atr_data1[0], self.sma_data1[0], self.atr_data1_pct[0])
        self.log_indicators(2, self.atr_data2[0], self.sma_data2[0], self.atr_data2_pct[0])
        self.log_indicators(3, self.atr_data3[0], self.sma_data3[0], self.atr_data3_pct[0])
        logger.info('----------------------')
