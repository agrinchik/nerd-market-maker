import backtrader as bt
import backtrader.indicators as btind
from market_maker.utils import log
from market_maker.backtrader.utils import UTC_to_CurrTZ
from market_maker.backtrader.ccxtbt import CCXTFeed
import math

logger = log.setup_supervisor_custom_logger('root')


class MarketRegimeIndicator(bt.Indicator):
    '''
    This is an implementation of an indicator based on strategy from TradingView - S002 Alex (Noro) SILA v1.6.1L strategy.
    '''
    lines = ('marketregime',
             'trends'
    )

    params = (
        ("sensup", 2),
        ("sensdn", 2),
        ("usewow", True),
        ("usebma", True),
        ("usebc", True),
        ("usest", True),
        ("usedi", True),
        ("usetts", True),
        ("usersi", True),
        ("usewto", True),
        ("usemacdind1", True),
        ("usemacdind2", True),
        ("useis", True),
        ("useev", True),
        ("usealw", True),
    )

    def _nz(self, data_arr, idx):
        if len(data_arr) < (abs(idx) + 1):
            return 0
        else:
            return data_arr[idx]

    def __init__(self):
        self.curr_data_len = 0

        # WOW 1.0 method
        self.lasthigh = btind.Highest(self.data.close, period=30)
        self.lastlow = btind.Lowest(self.data.close, period=30)
        self.center = [0.0]
        self.trend1 = [0, 0]
        self.trend2 = [0, 0]
        self.WOWtrend = [0, 0]

        # BestMA 1.0 method
        self.SMAOpen = bt.talib.SMA(self.data.open, timeperiod=30)
        self.SMAClose = bt.talib.SMA(self.data.close, timeperiod=30)
        self.BMAtrend = [0, 0]

        # BarColor 1.0 method
        self.color = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.BARtrend = [0, 0]

        # SuperTrend mehtod
        self.Atr3 = btind.AverageTrueRange(self.data, period=3)
        self.TrendUp = [0, 0, 0]
        self.TrendDn = [0, 0, 0]
        self.SUPtrend = [0, 0]

        # DI method
        self.TrueRange = btind.TrueRange(self.data)
        self.DirectionalMovementPlus = [0, 0]
        self.DirectionalMovementMinus = [0, 0]
        self.SmoothedTrueRange = [0.0, 0.0]
        self.SmoothedDirectionalMovementPlus = [0.0, 0.0]
        self.SmoothedDirectionalMovementMinus = [0.0, 0.0]
        self.DIPlus = [0.0, 0.0]
        self.DIMinus = [0.0, 0.0]
        self.DItrend = [0, 0]

        # TTS method(Trend Trader Strategy)
        # Start of HPotter's code
        # Andrew Abraham' idea
        self.Atr1 = btind.AverageTrueRange(self.data, period=1)
        self.avgTR = btind.WeightedMovingAverage(self.Atr1, period=21)
        self.highestC = btind.Highest(self.data.high, period=21)
        self.lowestC = btind.Lowest(self.data.low, period=21)
        self.ret = [0, 0]
        self.pos = [0, 0]
        # End of HPotter 's code
        self.TTStrend = [0, 0]

        # RSI method
        self.RSI13 = btind.RSI(self.data.close, period=13, safediv=True)
        self.RSItrend = [0, 0]

        # WTO("WaveTrend Oscilator") method by LazyBear
        # Start of LazyBear's code
        self.hlc3 = (self.data.high + self.data.low + self.data.close) / 3
        self.esa = btind.ExponentialMovingAverage(self.hlc3, period=10)
        self.hlc3esa = abs(self.hlc3 - self.esa)
        self.d = btind.ExponentialMovingAverage(self.hlc3esa, period=10)
        self.ci = (self.hlc3 - self.esa) / (0.015 * self.d)
        self.tci = btind.ExponentialMovingAverage(self.ci, period=21)
        # End of LazyBear's code
        self.WTOtrend = [0, 0]

        # Using MACD indicator: rising/falling MACD value - bullish/bearish market
        self.macd_ind = btind.MACDHisto(self.data, period_me1=12, period_me2=26, period_signal=9)
        self.MACDtrend1 = [0, 0]

        # Using MACD indicator: MACD value above/below zero - bullish/bearish market
        self.MACDtrend2 = [0, 0]

        # Impulse System - bullish/bearish/range market
        self.ema_val = btind.ExponentialMovingAverage(self.data.close, period=13)
        self.IStrend = [0, 0]

        # Noro's ElectroVanga v2.0
        self.evLasthigh = btind.Highest(self.data.close, period=30)
        self.evLastlow = btind.Lowest(self.data.close, period=30)
        self.EVtrend = [0, 0]
        ########### INDICATORS SECTION END ########

    def next(self):
        if len(self.data) <= self.curr_data_len:
            return
        else:
            self.curr_data_len = len(self.data)

        granularity = self.data.get_granularity()[0]
        logger.debug("MarketRegimeIndicator.next(): len(self.data)={}, granularity={}".format(len(self.data), granularity))

        # WOW 1.0 method
        self.center.append((self.lasthigh[0] + self.lastlow[0]) / 2)
        body = (self.data.open[0] + self.data.close[0]) / 2
        if body > self.center[-1]:
            self.trend1.append(1)
        else:
            if body < self.center[-1]:
                self.trend1.append(-1)
            else:
                self.trend1.append(self.trend1[-1])
        if self.center[-1] > self.center[-2]:
            self.trend2.append(1)
        else:
            if self.center[-1] < self.center[-2]:
                self.trend2.append(-1)
            else:
                self.trend2.append(self.trend2[-1])

        if self.p.usewow is True:
            if self.trend1[-1] == 1 and self.trend2[-1] == 1:
                self.WOWtrend.append(1)
            else:
                if self.trend1[-1] == -1 and self.trend2[-1] == -1:
                    self.WOWtrend.append(-1)
                else:
                    self.WOWtrend.append(self.WOWtrend[-1])
        else:
            self.WOWtrend.append(0)

        # BestMA 1.0 method
        if self.p.usebma is True:
            if self.SMAClose[0] > self.SMAOpen[0]:
                self.BMAtrend.append(1)
            else:
                if self.SMAClose[0] < self.SMAOpen[0]:
                    self.BMAtrend.append(-1)
                else:
                    self.BMAtrend.append(self.BMAtrend[-1])
        else:
            self.BMAtrend.append(0)

        # BarColor 1.0 method
        if self.data.close[0] > self.data.open[0]:
            self.color.append(1)
        else:
            self.color.append(0)
        score = self.color[-1] + self.color[-2] + self.color[-3] + self.color[-4] + self.color[-5] + self.color[-6] + self.color[-7] + self.color[-8]
        if self.p.usebc is True:
            if score > 5:
                self.BARtrend.append(1)
            else:
                if score < 3:
                    self.BARtrend.append(-1)
                else:
                    self.BARtrend.append(self.BARtrend[-1])
        else:
            self.BARtrend.append(0)

        # SuperTrend mehtod
        Up = (self.data.high[0] + self.data.low[0]) / 2 - (7 * self.Atr3[0])
        Dn = (self.data.high[0] + self.data.low[0]) / 2 + (7 * self.Atr3[0])
        if self.data.close[-1] > self.TrendUp[-1]:
            self.TrendUp.append(max(Up, self.TrendUp[-1]))
        else:
            self.TrendUp.append(Up)
        if self.data.close[-1] < self.TrendDn[-1]:
            self.TrendDn.append(min(Dn, self.TrendDn[-1]))
        else:
            self.TrendDn.append(Dn)
        if self.p.usest is True:
            if self.data.close[0] > self.TrendDn[-2]:
                self.SUPtrend.append(1)
            else:
                if self.data.close[0] < self.TrendUp[-2]:
                    self.SUPtrend.append(-1)
                else:
                    self.SUPtrend.append(self.SUPtrend[-1])
        else:
            self.SUPtrend.append(0)

        # DI method
        if self.data.high[0] - self._nz(self.data.high, -1) > self._nz(self.data.low, -1) - self.data.low[0]:
            self.DirectionalMovementPlus.append(max(self.data.high[0] - self._nz(self.data.high, -1), 0))
        else:
            self.DirectionalMovementPlus.append(0)
        if self._nz(self.data.low, -1) - self.data.low[0] > self.data.high[0] - self._nz(self.data.high, -1):
            self.DirectionalMovementMinus.append(max(self._nz(self.data.low, -1) - self.data.low[0], 0))
        else:
            self.DirectionalMovementMinus.append(0)
        self.SmoothedTrueRange.append(self._nz(self.SmoothedTrueRange, -1) - (self._nz(self.SmoothedTrueRange, -1) / 14) + self.TrueRange[0])
        self.SmoothedDirectionalMovementPlus.append(self._nz(self.SmoothedDirectionalMovementPlus, -1) - (self._nz(self.SmoothedDirectionalMovementPlus, -1) / 14) + self.DirectionalMovementPlus[-1])
        self.SmoothedDirectionalMovementMinus.append(self._nz(self.SmoothedDirectionalMovementMinus, -1) - (self._nz(self.SmoothedDirectionalMovementMinus, -1) / 14) + self.DirectionalMovementMinus[-1])
        self.DIPlus.append(self.SmoothedDirectionalMovementPlus[-1] / self.SmoothedTrueRange[-1] * 100 if self.SmoothedTrueRange[-1] != 0 else 0)
        self.DIMinus.append(self.SmoothedDirectionalMovementMinus[-1] / self.SmoothedTrueRange[-1] * 100 if self.SmoothedTrueRange[-1] != 0 else 0)
        if self.p.usedi is True:
            if self.DIPlus[-1] > self.DIMinus[-1]:
                self.DItrend.append(1)
            else:
                self.DItrend.append(-1)
        else:
            self.DItrend.append(0)

        # TTS method(Trend Trader Strategy)
        hiLimit = self.highestC[-1] - (self.avgTR[-1] * 3)
        loLimit = self.lowestC[-1] + (self.avgTR[-1] * 3)
        if self.data.close[0] > hiLimit and self.data.close[0] > loLimit:
            self.ret.append(hiLimit)
        else:
            if self.data.close[0] < loLimit and self.data.close[0] < hiLimit:
                self.ret.append(loLimit)
            else:
                self.ret.append(self._nz(self.ret, -1))
        if self.data.close[0] > self.ret[-1]:
            self.pos.append(1)
        else:
            if self.data.close[0] < self.ret[-1]:
                self.pos.append(-1)
            else:
                self.pos.append(self._nz(self.pos, -1))
        # End of HPotter 's code

        if self.p.usetts is True:
            if self.pos[-1] == 1:
                self.TTStrend.append(1)
            else:
                if self.pos[-1] == -1:
                    self.TTStrend.append(-1)
                else:
                    self.TTStrend.append(self.TTStrend[-1])
        else:
            self.TTStrend.append(0)

        # RSI method
        RSIMain = (self.RSI13 - 50) * 1.5
        if self.p.usersi is True:
            if RSIMain > -10:
                self.RSItrend.append(1)
            else:
                if RSIMain < 10:
                    self.RSItrend.append(-1)
                else:
                    self.RSItrend.append(self._nz(self.pos, -1))
        else:
            self.RSItrend.append(0)

        # WTO("WaveTrend Oscilator") method
        if self.p.usewto is True:
            if self.tci[0] > 0:
                self.WTOtrend.append(1)
            else:
                if self.tci[0] < 0:
                    self.WTOtrend.append(-1)
                else:
                    self.WTOtrend.append(0)
        else:
            self.WTOtrend.append(0)

        # Using MACD indicator: rising/falling MACD value - bullish/bearish market
        if self.p.usemacdind1 is True:
            if self.macd_ind.macd[0] > self.macd_ind.macd[-1]:
                self.MACDtrend1.append(1)
            else:
                if self.macd_ind.macd[0] < self.macd_ind.macd[-1]:
                    self.MACDtrend1.append(-1)
                else:
                    self.MACDtrend1.append(self.MACDtrend1[-1])
        else:
            self.MACDtrend1.append(0)

        # Using MACD indicator: MACD value above/below zero - bullish/bearish market
        if self.p.usemacdind2 is True:
            if self.macd_ind.macd[0] > 0:
                self.MACDtrend2.append(1)
            else:
                if self.macd_ind.macd[0] < 0:
                    self.MACDtrend2.append(-1)
                else:
                    self.MACDtrend2.append(self.MACDtrend2[-1])
        else:
            self.MACDtrend2.append(0)

        # Impulse System - bullish/bearish/range market
        if self.p.useis is True:
            if self.macd_ind.histo[0] > self.macd_ind.histo[-1] and self.ema_val[0] > self.ema_val[-1]:
                self.IStrend.append(1)
            else:
                if self.macd_ind.histo[0] < self.macd_ind.histo[-1] and self.ema_val[0] < self.ema_val[-1]:
                    self.IStrend.append(-1)
                else:
                    self.IStrend.append(self.IStrend[-1])
        else:
            self.IStrend.append(0)

        # Noro's ElectroVanga v2.0
        if self.p.useev is True:
            evCenter = (self.evLasthigh[0] + self.evLastlow[0]) / 2
            if self.data.low[0] > evCenter:
                self.EVtrend.append(1)
            else:
                if self.data.high[0] < evCenter:
                    self.EVtrend.append(-1)
                else:
                    self.EVtrend.append(self.EVtrend[-1])
        else:
            self.EVtrend.append(0)

        trends_sum = self.WOWtrend[-1] + self.BMAtrend[-1] + self.BARtrend[-1] + self.SUPtrend[-1] + self.DItrend[-1] + self.TTStrend[-1] + self.RSItrend[-1] + self.WTOtrend[-1] + self.MACDtrend1[-1] + self.MACDtrend2[-1] + self.IStrend[-1] + self.EVtrend[-1]
        self.l.trends[0] = trends_sum

        prev_marketregime = self.l.marketregime[0]
        is_nan = math.isnan(prev_marketregime)

        if trends_sum >= self.p.sensup:
            self.l.marketregime[0] = 1
        else:
            if trends_sum <= (-1 * self.p.sensdn):
                self.l.marketregime[0] = -1
            else:
                try:
                    if self.p.usealw is True and is_nan is False:
                        self.l.marketregime[0] = prev_marketregime
                    else:
                        self.l.marketregime[0] = 0
                except Exception as e:
                    logger.info("Strange exception occurred: {}".format(e))
                    self.l.marketregime[0] = 0
        logger.info("prev_marketregime={}, is_nan={}, trends_sum={}, self.p.sensup={}, self.p.sensdn={}, self.p.usealw={}, self.l.trends[0]={}. Resolved self.l.marketregime[0]={}".format(prev_marketregime, is_nan, trends_sum, self.p.sensup, self.p.sensdn, self.p.usealw, self.l.trends[0], self.l.marketregime[0]))


class MM001_MarketSnapshotStrategy(bt.Strategy):
    params = (
        ("debug", False),
    )

    def __init__(self):
        self.status = CCXTFeed._getstatusname(CCXTFeed.UNKNOWN)
        self.market_regime_5m = MarketRegimeIndicator(self.data1)
        self.market_regime_1h = MarketRegimeIndicator(self.data2)
        self.market_regime_1D = MarketRegimeIndicator(self.data3)

    def get_last_ohlc_val(self, line):
        return line[0] if line[0] and not math.isnan(line[0]) else line[-1]

    def get_market_snapshot(self):
        result = {}
        datas = self.datas
        result["Indicators"] = {}
        ind_entry = result["Indicators"]["Market Regime"] = {}
        ind_entry["5m.trends"] = self.market_regime_5m.trends[0]
        ind_entry["5m.marketregime"] = self.market_regime_5m.marketregime[0]
        ind_entry["1h.trends"] = self.market_regime_1h.trends[0]
        ind_entry["1h.marketregime"] = self.market_regime_1h.marketregime[0]
        ind_entry["1D.trends"] = self.market_regime_1D.trends[0]
        ind_entry["1D.marketregime"] = self.market_regime_1D.marketregime[0]
        ind_entry["marketregime"] = self.market_regime_5m.marketregime[0]
        ind_entry["marketregime_hist"] = [self.market_regime_5m.marketregime[-4], self.market_regime_5m.marketregime[-3], self.market_regime_5m.marketregime[-2], self.market_regime_5m.marketregime[-1], self.market_regime_5m.marketregime[0]]
        result["OHLCV"] = {}
        for i, data in enumerate(datas):
            key = "data{}".format(i)
            ohlcv = [
                        self.get_last_ohlc_val(data.open),
                        self.get_last_ohlc_val(data.high),
                        self.get_last_ohlc_val(data.low),
                        self.get_last_ohlc_val(data.close),
                        self.get_last_ohlc_val(data.volume)
                    ]
            result["OHLCV"][key] = ohlcv
        return result

    def is_datas_live(self):
        for d in self.datas:
            if not d.islive():
                return False
        return True

    def is_live_status(self):
        return self.status == self.data._getstatusname(CCXTFeed.LIVE)

    def is_all_datas_live_state(self):
        for d in self.datas:
            if d._state != CCXTFeed._ST_LIVE:
                return False
        return True

    def notify_data(self, data, new_status, *args, **kwargs):
        logger.debug("notify_data() - current status={}, new status={}".format(self.status, self.data._getstatusname(new_status)))
        if new_status != CCXTFeed.LIVE:
            self.status = self.data._getstatusname(new_status)
        if new_status == data.LIVE and self.is_datas_live() and self.is_all_datas_live_state():
            self.status = self.data._getstatusname(CCXTFeed.LIVE)
            logger.debug("**** Initialized the Backtrader in LIVE mode: {} ****".format(self.data.symbol))
            logger.debug("=" * 120)
            logger.debug("LIVE DATA - MM001_MarketSnapshotStrategy initialized")
            logger.debug("=" * 120)

    def next(self):
        try:
            logger.debug("MM001_MarketSnapshotStrategy.next(): status={}, len(datas[0])={}, len(datas[1])={}, len(datas[2])={}, len(datas[3])={}".format(
                self.status, len(self.datas[0]), len(self.datas[1]), len(self.datas[2]), len(self.datas[3])))

            if self.is_datas_live() and not self.is_live_status():
                logger.info("%s - %.8f" % (self.status, self.data0.close[0]))
                return

            self.print_all_debug_info()
        except Exception as e:
            self.broker.cerebro.runstop()
            raise e

    def log_data(self, idx, data):
        logger.debug("len(self.data{})={}".format(idx, len(data)))
        logger.debug('self.data{}.datetime[0] = {}'.format(idx, UTC_to_CurrTZ(data.datetime.datetime(0))))
        logger.debug('self.data{}.open[0] = {}'.format(idx, data.open[0]))
        logger.debug('self.data{}.high[0] = {}'.format(idx, data.high[0]))
        logger.debug('self.data{}.low[0] = {}'.format(idx, data.low[0]))
        logger.debug('self.data{}.close[0] = {}'.format(idx, data.close[0]))
        logger.debug('self.data{}.volume[0] = {}'.format(idx, data.volume[0]))

    def print_all_debug_info(self):
        logger.debug('---------------------- INSIDE NEXT DEBUG --------------------------')
        self.log_data(0, self.data0)
        self.log_data(1, self.data1)
        self.log_data(2, self.data2)
        self.log_data(3, self.data3)
        logger.debug('self.market_regime_5m.trends = {}'.format(self.market_regime_5m.trends[0]))
        logger.debug('self.market_regime_5m.marketregime = {}'.format(self.market_regime_5m.marketregime[0]))
        logger.debug('self.market_regime_1h.trends = {}'.format(self.market_regime_1h.trends[0]))
        logger.debug('self.market_regime_1h.marketregime = {}'.format(self.market_regime_1h.marketregime[0]))
        logger.debug('self.market_regime_1D.trends = {}'.format(self.market_regime_1D.trends[0]))
        logger.debug('self.market_regime_1D.marketregime = {}'.format(self.market_regime_1D.marketregime[0]))
        logger.debug('----------------------')
