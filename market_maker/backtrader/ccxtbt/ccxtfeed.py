#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015, 2016, 2017 Daniel Rodriguez
# Copyright (C) 2017 Ed Bartosh
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import time
from collections import deque
from datetime import datetime, timedelta

import backtrader as bt
from backtrader.feed import DataBase
from backtrader.utils.py3 import with_metaclass
from market_maker.utils import log

from .ccxtstore import CCXTStore

logger = log.setup_supervisor_custom_logger('root')


class MetaCCXTFeed(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaCCXTFeed, cls).__init__(name, bases, dct)

        # Register with the store
        CCXTStore.DataCls = cls


class CCXTFeed(with_metaclass(MetaCCXTFeed, DataBase)):
    """
    CryptoCurrency eXchange Trading Library Data Feed.
    Params:
      - ``historical`` (default: ``False``)
        If set to ``True`` the data feed will stop after doing the first
        download of data.
        The standard data feed parameters ``fromdate`` and ``todate`` will be
        used as reference.
      - ``backfill_start`` (default: ``True``)
        Perform backfilling at the start. The maximum possible historical data
        will be fetched in a single request.

    Changes From Ed's pacakge

        - Added option to send some additional fetch_ohlcv_params. Some exchanges (e.g Bitmex)
          support sending some additional fetch parameters. 

    """

    params = (
        ('historical', False),  # only historical download
        ('backfill_start', False),  # do backfilling at the start
        ('fetch_ohlcv_params', {}),
        ('ohlcv_limit', 20),
        ('merge_partial_live_bars', False),
    )

    _store = CCXTStore

    # States for the Finite State Machine in _load
    _ST_LIVE, _ST_HISTORBACK, _ST_OVER = range(3)

    # def __init__(self, exchange, symbol, ohlcv_limit=None, config={}, retries=5):
    def __init__(self, **kwargs):
        self.symbol = self.p.dataname
        # self.store = CCXTStore(exchange, config, retries)
        self.store = self._store(**kwargs)
        self._data = deque()  # data queue for price data
        self._last_id = ''  # last processed trade id for ohlcv
        self._last_ts = 0  # last processed timestamp for ohlcv

    def get_granularity(self):
        return self.store.get_granularity(self._timeframe, self._compression)

    def start(self, ):
        DataBase.start(self)

        if self.p.fromdate:
            self._state = self._ST_HISTORBACK
            self.put_notification(self.DELAYED)
            self._fetch_ohlcv(self.p.fromdate)

        else:
            self._state = self._ST_LIVE
            self.put_notification(self.LIVE)

    def check_all_datas_live(self):
        _cerebro = self.store.cerebro
        strategy = _cerebro.runningstrats[0] if len(_cerebro.strats) > 0 and len(_cerebro.runningstrats) > 0 else None
        return strategy.is_all_datas_live_state()

    def _load(self):
        if self._state == self._ST_OVER:
            return False

        while True:
            if self._state == self._ST_LIVE:
                if self._timeframe == bt.TimeFrame.Ticks:
                    return self._load_ticks()
                else:
                    if self.check_all_datas_live():
                        if self.p.merge_partial_live_bars:
                            self._fetch_partial_ohlcv()
                            ret = self._merge_ohlcvs()
                        else:
                            self._fetch_ohlcv()
                            ret = self._load_ohlcv()
                        logger.debug('--- Load OHLCV Returning: {}'.format(ret))
                        return ret
                    else:
                        return None

            elif self._state == self._ST_HISTORBACK:
                ret = self._load_ohlcv()
                if ret:
                    return ret
                else:
                    # End of historical data
                    if self.p.historical:  # only historical
                        self.put_notification(self.DISCONNECTED)
                        self._state = self._ST_OVER
                        return False  # end of historical
                    else:
                        self._state = self._ST_LIVE
                        self.put_notification(self.LIVE)
                        continue

    def _fetch_ohlcv(self, fromdate=None):
        """Fetch OHLCV data into self._data queue"""
        logger.debug('_fetch_ohlcv() - BEGIN')
        logger.debug('self._last_ts={}, self._state={}'.format(datetime.fromtimestamp(self._last_ts // 1000), self._state))
        granularity = self.get_granularity()[0]
        if fromdate:
            since = int((fromdate - datetime(1970, 1, 1)).total_seconds() * 1000)
        else:
            if self._last_ts > 0:
                since = self._last_ts
            else:
                since = None

        limit = self.p.ohlcv_limit

        since_dt = datetime.fromtimestamp(since // 1000) if since is not None else 'NA'
        logger.debug('---- NEW REQUEST ----')
        logger.debug('{} - Requesting: Since TS {} Since date {} granularity {}, limit {}, params'.format(
            datetime.utcnow(), since, since_dt, granularity, limit, self.p.fetch_ohlcv_params))
        data = sorted(self.store.fetch_ohlcv(self.p.dataname, timeframe=granularity,
                                             since=since, limit=limit, params=self.p.fetch_ohlcv_params))
        try:
            for i, ohlcv in enumerate(data):
                tstamp, open_, high, low, close, volume = ohlcv
                logger.debug('{} - Data {}: {} - TS {} Time {} [{}, {}, {}, {}, {}, {}]'.format(datetime.utcnow(), i, datetime.fromtimestamp(tstamp // 1000),
                    tstamp, (time.time() * 1000), datetime.fromtimestamp(tstamp // 1000), open_, high, low, close, volume))
        except IndexError:
            logger.debug('Index Error: Data = {}'.format(data))
        logger.debug('---- REQUEST END ----')

        for ohlcv in data:
            if None in ohlcv:
                continue
            tstamp = ohlcv[0]
            if tstamp > self._last_ts:
                tstamp_val_epoch = tstamp / 1000
                tstamp_dt = datetime.fromtimestamp(tstamp_val_epoch).strftime('%Y-%m-%d %H:%M:%S')
                logger.debug('Adding OHLCV {}: timestamp={}, ohlcv={}'.format(granularity, tstamp_dt, ohlcv))
                self._data.append(ohlcv)
                self._last_ts = tstamp

    def _fetch_partial_ohlcv(self):
        logger.debug('_fetch_partial_ohlcv() - BEGIN')
        logger.debug('self._last_ts={}, self._state={}'.format(datetime.fromtimestamp(self._last_ts // 1000), self._state))
        granularity_info = self.get_granularity()
        granularity = granularity_info[0]
        granularity_duration_msec = granularity_info[1] / timedelta(milliseconds=1)

        if self._last_ts > 0:
            since = self._last_ts - granularity_duration_msec  # Workaround for BitMEX - fetch extra bar to get the most up-to-date partial bar
        else:
            since = None

        limit = self.p.ohlcv_limit
        since_dt = datetime.fromtimestamp(since // 1000) if since is not None else 'NA'
        logger.debug('---- NEW REQUEST ----')
        logger.debug('{} - Requesting partial OHLCV: Since TS {} Since date {} granularity {}, limit {}, params'.format(
            datetime.utcnow(), since, since_dt, granularity, limit, self.p.fetch_ohlcv_params))
        data = sorted(self.store.fetch_ohlcv(self.p.dataname, timeframe=granularity, since=since, limit=limit, params=self.p.fetch_ohlcv_params))

        try:
            for i, ohlcv in enumerate(data):
                tstamp, open_, high, low, close, volume = ohlcv
                logger.debug('{} - Data {}: {} - TS {} Time {} [{}, {}, {}, {}, {}, {}]'.format(datetime.utcnow(), i, datetime.fromtimestamp(tstamp // 1000),
                    tstamp, (time.time() * 1000), datetime.fromtimestamp(tstamp // 1000), open_, high, low, close, volume))
        except IndexError:
            logger.debug('Index Error: Data = {}'.format(data))
        logger.debug('---- REQUEST END ----')

        for ohlcv in data:
            tstamp = ohlcv[0]
            tstamp_val_epoch = tstamp / 1000
            tstamp_dt = datetime.fromtimestamp(tstamp_val_epoch).strftime('%Y-%m-%d %H:%M:%S')
            logger.debug('Adding OHLCV {}: timestamp={}, ohlcv={}'.format(granularity, tstamp_dt, ohlcv))
            self._data.append(ohlcv)
            self._last_ts = tstamp

    def _load_ticks(self):
        if self._last_id is None:
            # first time get the latest trade only
            trades = [self.store.fetch_trades(self.symbol)[-1]]
        else:
            trades = self.store.fetch_trades(self.symbol)

        for trade in trades:
            trade_id = trade['id']

            if trade_id > self._last_id:
                trade_time = datetime.strptime(trade['datetime'], '%Y-%m-%dT%H:%M:%S.%fZ')
                self._data.append((trade_time, float(trade['price']), float(trade['amount'])))
                self._last_id = trade_id

        try:
            trade = self._data.popleft()
        except IndexError:
            return None  # no data in the queue

        trade_time, price, size = trade

        self.lines.datetime[0] = bt.date2num(trade_time)
        self.lines.open[0] = price
        self.lines.high[0] = price
        self.lines.low[0] = price
        self.lines.close[0] = price
        self.lines.volume[0] = size

        return True

    def _load_ohlcv(self):
        try:
            ohlcv = self._data.popleft()
        except IndexError:
            logger.debug("_load_ohlcv(): IndexError - no data in the queue - returning None")
            return None  # no data in the queue

        tstamp, open_, high, low, close, volume = ohlcv

        dtime = datetime.utcfromtimestamp(tstamp // 1000)

        self.lines.datetime[0] = bt.date2num(dtime)
        self.lines.open[0] = open_
        self.lines.high[0] = high
        self.lines.low[0] = low
        self.lines.close[0] = close
        self.lines.volume[0] = volume

        return True

    def find_ohlcv_idx_by_datetime(self, dt_line, ohlcv_dt, len):
        for i in range(0, -len, -1):
            if dt_line[i] == ohlcv_dt:
                return i

        return None

    def _merge_ohlcvs(self):
        result = None
        data_copy_list = self._data.copy()
        for i in data_copy_list:
            ohlcv = self._data.popleft()
            logger.debug("_merge_ohlcvs(): Processing OHLCV={}".format(ohlcv))
            tstamp, open_, high, low, close, volume = ohlcv

            if volume == 0:
                logger.debug("_merge_ohlcvs(): OHLCV record has zero volume - skipping record")
                continue

            dtime = datetime.utcfromtimestamp(tstamp // 1000)
            ohlcv_dt = bt.date2num(dtime)
            idx = self.find_ohlcv_idx_by_datetime(self.lines.datetime, ohlcv_dt, len(data_copy_list) + 1)
            if idx:
                if volume > self.lines.volume[idx]:
                    logger.debug("_merge_ohlcvs(): Found existing OHLCV record with updated volume in self.lines: idx={}, self.lines.datetime[{}]={} - OHLCV data will be merged".format(idx, idx, self.lines.datetime[idx]))
                    self.lines.datetime[idx] = ohlcv_dt
                    self.lines.open[idx] = open_ if open_ else self.lines.open[idx]
                    self.lines.high[idx] = high if high else self.lines.high[idx]
                    self.lines.low[idx] = low if low else self.lines.low[idx]
                    self.lines.close[idx] = close if close else self.lines.close[idx]
                    self.lines.volume[idx] = volume if volume else self.lines.volume[idx]
                    logger.debug("_merge_ohlcvs(): Merged OHLCV data into self.lines[{}]: {}".format(idx, ohlcv))
                else:
                    logger.debug("_merge_ohlcvs(): Found existing OHLCV record in self.lines but volume is the same: idx={}, self.lines.datetime[{}]={} - skipping record".format(idx, idx, self.lines.datetime[idx]))
            else:
                logger.debug("_merge_ohlcvs(): The OHLCV record is not found in self.lines.datetime - the record will be added")
                if None in ohlcv:
                    logger.debug("_merge_ohlcvs(): The record being added contains incomplete data (None) - skipping record")
                    continue

                self.lines.datetime[0] = ohlcv_dt
                self.lines.open[0] = open_
                self.lines.high[0] = high
                self.lines.low[0] = low
                self.lines.close[0] = close
                self.lines.volume[0] = volume
                logger.debug("_merge_ohlcvs(): Added new OHLCV record into self.lines[0]: {}".format(ohlcv))
                result = True
                break

        return result

    def islive(self):
        return not self.p.historical
