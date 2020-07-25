

from market_maker.strategies.genericstrategy import GenericStrategy
from market_maker.settings import settings
from market_maker.utils import mm_math
from market_maker.db.quoting_side import *
import requests

from time import sleep

TP_NUM_TICKS_FACTOR = 0
INTERVAL_NUM_TICKS_FACTOR = 0
RELIST_INTERVAL_NUM_TICKS_FACTOR = 1

LIVE_POSITION_ADJUST_MULT = 3


class MM002_OrderMakerStrategy(GenericStrategy):

    def __init__(self, logger, exchange):
        super().__init__(logger, exchange)

    def check_suspend_trading(self):
        pass

    def place_orders(self):
        """Create order items for use in convergence."""
        buy_orders = []
        sell_orders = []

        running_qty = self.exchange.get_delta()
        if running_qty != 0:
            if running_qty > 0:
                sell_orders.append(self.prepare_tp_order(True, running_qty))
            else:
                buy_orders.append(self.prepare_tp_order(False, running_qty))
        else:
            quoting_side = settings.QUOTING_SIDE
            if self.is_quoting_side_ok(True, quoting_side):
                buy_orders.append(self.prepare_order(-1))
            if self.is_quoting_side_ok(False, quoting_side):
                sell_orders.append(self.prepare_order(1))

        return self.converge_orders(buy_orders, sell_orders)

    def override_parameters(self):
        pass

    def update_dynamic_app_settings(self, force_update):
        self.dynamic_settings.update_app_settings(self.curr_market_snapshot, force_update)
        self.override_parameters()

    def get_tp_price(self, is_long, instrument, ticker_bid_price, ticker_ask_price):
        take_profit_num_ticks = TP_NUM_TICKS_FACTOR * instrument["tickSize"]
        if is_long:
            price = ticker_ask_price + take_profit_num_ticks
        else:
            price = ticker_bid_price - take_profit_num_ticks
        return price

    def get_price(self, index, instrument, ticker_bid_price, ticker_ask_price):
        interval_num_ticks = INTERVAL_NUM_TICKS_FACTOR * instrument["tickSize"]
        if index < 0:
            price = ticker_bid_price - interval_num_ticks
        else:
            price = ticker_ask_price + interval_num_ticks
        return price

    def get_quantity(self, is_long):
        if not is_long:
            return mm_math.roundQuantity(settings.MIN_POSITION / LIVE_POSITION_ADJUST_MULT)
        else:
            return mm_math.roundQuantity(settings.MAX_POSITION / LIVE_POSITION_ADJUST_MULT)

    def prepare_tp_order(self, is_long, quantity):
        instrument = self.exchange.get_instrument()
        symbol = self.exchange.symbol
        ticker = self.exchange.get_ticker(symbol)
        ticker_bid_price = ticker["buy"]
        ticker_ask_price = ticker["sell"]

        price = self.get_tp_price(is_long, instrument, ticker_bid_price, ticker_ask_price)
        side = "Sell" if is_long else "Buy"

        return {"price": price, "orderQty": -quantity, "side": side, "ordType": "Limit", "execInst": "ParticipateDoNotInitiate,ReduceOnly"}

    def prepare_order(self, index):
        """Create an order object."""
        instrument = self.exchange.get_instrument()
        minOrderLog = instrument.get("minOrderLog")
        symbol = self.exchange.symbol
        ticker = self.exchange.get_ticker(symbol)
        ticker_bid_price = ticker["buy"]
        ticker_ask_price = ticker["sell"]

        if index > 0:
            quantity = self.get_quantity(False)
        elif index < 0:
            quantity = self.get_quantity(True)
        else:
            quantity = 0

        price = self.get_price(index, instrument, ticker_bid_price, ticker_ask_price)
        side = "Buy" if index < 0 else "Sell"

        return {"price": price, "orderQty": quantity, "side": side, "ordType": "Limit", "execInst": "ParticipateDoNotInitiate"}

    def get_ticker(self):
        instrument = self.exchange.get_instrument()
        ticker = self.exchange.get_ticker()
        tickSize = instrument["tickSize"]
        tickLog = instrument['tickLog']

        # Midpoint, used for simpler order placement.
        self.start_position_mid = ticker["mid"]
        self.logger.debug("{} Ticker: Buy: {}, Sell: {}".format(instrument['symbol'], round(ticker["buy"], tickLog), round(ticker["sell"], tickLog)))
        self.logger.debug('Start Positions: Buy: {}, Sell: {}, Mid: {}'.format(self.start_position_buy, self.start_position_sell, self.start_position_mid))
        return ticker

    def find_order_with_params(self, orders, orderQty, side, ordType):
        lst = list(filter(lambda o: o["orderQty"] == orderQty and o["side"] == side and o["ordType"] == ordType, orders))
        if len(lst) > 0:
            return lst[0]

    def is_price_diff_exceeded_value(self, price1, price2, max_diff):
        return abs(price1 - price2) >= max_diff

    def compare_orders(self, existing_orders, desired_orders, instrument):
        to_create = []
        to_amend = []
        to_cancel = []
        relist_interval = RELIST_INTERVAL_NUM_TICKS_FACTOR * instrument["tickSize"]

        for d_order in desired_orders:
            matched_existing_order = self.find_order_with_params(existing_orders, abs(d_order["orderQty"]), d_order["side"], d_order["ordType"])
            if not matched_existing_order:
                to_create.append(d_order)
            else:
                is_price_exceeded = self.is_price_diff_exceeded_value(matched_existing_order["price"], d_order["price"], relist_interval)
                if is_price_exceeded:
                    d_order["orderID"] = matched_existing_order["orderID"]
                    to_amend.append(d_order)
                existing_orders = list(filter(lambda eo: eo["clOrdID"] != matched_existing_order["clOrdID"], existing_orders))

        if len(existing_orders) > 0:
            to_cancel = existing_orders.copy()

        return [to_create, to_amend, to_cancel]

    def converge_orders(self, buy_orders, sell_orders):
        instrument = self.exchange.get_instrument()
        existing_orders = self.exchange.get_orders()
        desired_orders = buy_orders + sell_orders

        [to_create, to_amend, to_cancel] = self.compare_orders(existing_orders, desired_orders, instrument)
        need_create = len(to_create) > 0
        need_amend = len(to_amend) > 0
        need_cancel = len(to_cancel) > 0

        if need_cancel:
            self.exchange.cancel_bulk_orders(to_cancel)

        if need_create:
            self.exchange.create_bulk_orders(desired_orders)

        if need_amend:
            try:
                self.exchange.amend_bulk_orders(to_amend)
            except Exception as e:
                sleep(0.1)
                return

        if need_create or need_amend or need_cancel:
            self.print_status(True)


    ###
    # Sanity
    ##
    def sanity_check(self):
        """Perform checks before placing orders."""
        # Check if OB is empty - if so, can't quote.
        self.exchange.check_if_orderbook_empty()

        # Ensure market is still open.
        self.exchange.check_market_open()

        # Messaging if the position limits are reached
        if self.long_position_limit_exceeded():
            self.logger.debug("Long delta limit exceeded")
            self.logger.debug("Current Position: {}, Maximum Position: {}".format(self.exchange.get_delta(), settings.MAX_POSITION))

        if self.short_position_limit_exceeded():
            self.logger.debug("Short delta limit exceeded")
            self.logger.debug("Current Position: {}, Minimum Position: {}".format(self.exchange.get_delta(), settings.MIN_POSITION))