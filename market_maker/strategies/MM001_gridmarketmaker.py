
from time import sleep
import sys
import requests
from datetime import datetime
from market_maker.strategies.genericstrategy import GenericStrategy
from market_maker.settings import settings
from market_maker.utils import log, mm_math
from market_maker.db.quoting_side import *
from market_maker.utils.log import log_debug
from market_maker.utils.log import log_info
from market_maker.utils.log import log_error
from common.exception import *
import numpy as np


class MM001_GridMarketMakerStrategy(GenericStrategy):

    def __init__(self, logger, exchange):
        super().__init__(logger, exchange)
        self.price_change_last_check = datetime.now()
        self.price_change_last_price = -1

    def check_suspend_trading(self):
        position_size = self.exchange.get_delta()
        if position_size == 0:
            return

        curr_time = datetime.now()
        symbol = self.exchange.symbol
        ticker = self.exchange.get_ticker(symbol)
        ticker_last_price = ticker["last"]
        price_change_last_checked_seconds_ago = (curr_time - self.price_change_last_check).total_seconds()
        price_change = ticker_last_price - self.price_change_last_price
        price_change_pct = abs(price_change * 100 / self.price_change_last_price)

        if settings.STOP_QUOTING_CHECK_IMPULSE_PRICE_CHANGE is True:
            if not self.is_trading_suspended:
                if self.price_change_last_price == -1:
                    self.price_change_last_check = curr_time
                    self.price_change_last_price = ticker_last_price
                    return

                if price_change_last_checked_seconds_ago > settings.STOP_QUOTING_PRICE_CHANGE_CHECK_TIME_PERIOD_SECONDS:
                    is_adverse_price_movement = True if np.sign(position_size) * np.sign(price_change) < 0 else False
                    if is_adverse_price_movement and price_change_pct > settings.STOP_QUOTING_PRICE_CHANGE_EXCEEDED_THRESHOLD_PCT:
                        log_info(self.logger, "WARNING: Trading would be SUSPENDED as during last {} seconds the {} price had moved very fast in the adverse direction and exceeded the threshold = {}%.".
                                 format(settings.STOP_QUOTING_PRICE_CHANGE_CHECK_TIME_PERIOD_SECONDS, symbol, settings.STOP_QUOTING_PRICE_CHANGE_EXCEEDED_THRESHOLD_PCT), True)
                        self.is_trading_suspended = True
                        self.exchange.cancel_all_orders()
                    self.price_change_last_check = curr_time
                    self.price_change_last_price = ticker_last_price
            else:
                if price_change_last_checked_seconds_ago > settings.RESUME_QUOTING_PRICE_CHANGE_CHECK_TIME_PERIOD_SECONDS:
                    if price_change_pct < settings.RESUME_QUOTING_PRICE_CHANGE_WENT_BELOW_THRESHOLD_PCT:
                        log_info(self.logger, "WARNING: Trading would be RESUMED as during last {} seconds the {} price had moved below the threshold = {}%".
                                 format(settings.RESUME_QUOTING_PRICE_CHANGE_CHECK_TIME_PERIOD_SECONDS, symbol, settings.RESUME_QUOTING_PRICE_CHANGE_WENT_BELOW_THRESHOLD_PCT), True)
                        self.is_trading_suspended = False
                    self.price_change_last_check = curr_time
                    self.price_change_last_price = ticker_last_price

    def place_orders(self):
        """Create order items for use in convergence."""
        buy_orders = []
        sell_orders = []

        self.running_qty = self.exchange.get_delta()
        if settings.WORKING_MODE == settings.MODE2_ALWAYS_CLOSE_FULL_POSITION_STRATEGY and self.running_qty != 0:
            if self.running_qty > 0:
                sell_orders.append(self.prepare_tp_order(True, abs(self.running_qty)))
                for i in reversed(range(1, settings.ORDER_PAIRS + 1)):
                    if not self.long_position_limit_exceeded():
                        buy_orders.append(self.prepare_order(-i))
            else:
                buy_orders.append(self.prepare_tp_order(False, abs(self.running_qty)))
                for i in reversed(range(1, settings.ORDER_PAIRS + 1)):
                    if not self.short_position_limit_exceeded():
                        sell_orders.append(self.prepare_order(i))
        else:
            # Create orders from the outside in. This is intentional - let's say the inner order gets taken;
            # then we match orders from the outside in, ensuring the fewest number of orders are amended and only
            # a new order is created in the inside. If we did it inside-out, all orders would be amended
            # down and a new order would be created at the outside.
            for i in reversed(range(1, settings.ORDER_PAIRS + 1)):
                if not self.long_position_limit_exceeded():
                    buy_orders.append(self.prepare_order(-i))
                if not self.short_position_limit_exceeded():
                    sell_orders.append(self.prepare_order(i))

        if self.is_trading_suspended is True:
            return

        return self.converge_orders(buy_orders, sell_orders)

    def prepare_order(self, index):
        """Create an order object."""

        instrument = self.exchange.get_instrument()
        minOrderLog = instrument.get("minOrderLog")
        quantity = mm_math.roundQuantity(settings.ORDER_START_SIZE + ((abs(index) - 1) * settings.ORDER_STEP_SIZE), minOrderLog)

        price = self.get_price_offset(index)

        return {'price': price, 'orderQty': quantity, 'side': "Buy" if index < 0 else "Sell"}

    def prepare_tp_order(self, is_long, quantity):
        instrument = self.exchange.get_instrument()
        position = self.exchange.get_position()
        avg_entry_price = position['avgEntryPrice']
        take_profit_pct = settings.MODE2_CLOSE_FULL_POSITION_ATR_MULT * self.curr_market_snapshot.atr_pct
        if is_long:
            price = avg_entry_price + avg_entry_price * take_profit_pct
        else:
            price = avg_entry_price - avg_entry_price * take_profit_pct
        price = mm_math.toNearest(price, instrument['tickSize'])

        return {'price': price, 'orderQty': quantity, 'side': "Sell" if is_long is True else "Buy"}

    def is_order_placement_allowed(self, order, quoting_side):
        result = True
        position = self.exchange.get_position()
        position_avg_price = position['avgEntryPrice']
        position_qty = position['currentQty']
        is_order_long = True if order["side"] == "Buy" else False
        order_price = order["price"]

        if not settings.STOP_QUOTING_IF_INSIDE_LOSS_RANGE or position_qty == 0:
            if self.is_quoting_side_ok(is_order_long, quoting_side):
                result = True
            else:
                result = False
        else:
            if position_qty > 0:
                if is_order_long:
                    if self.is_quoting_side_ok(is_order_long, quoting_side):
                        result = True
                    else:
                        result = False
                else:
                    if order_price >= position_avg_price:
                        result = True
                    else:
                        result = False
            else:
                if not is_order_long:
                    if self.is_quoting_side_ok(is_order_long, quoting_side):
                        result = True
                    else:
                        result = False
                else:
                    if order_price <= position_avg_price:
                        result = True
                    else:
                        result = False

        log_debug(self.logger, "is_order_placement_allowed(): order={}, result={}".format(order, result), False)
        return result

    def update_dynamic_app_settings(self, force_update):
        result = self.dynamic_settings.update_app_settings(self.curr_market_snapshot, force_update)

        if result:
            self.exchange.cancel_all_orders()

    def converge_orders(self, buy_orders, sell_orders):
        """Converge the orders we currently have in the book with what we want to be in the book.
           This involves amending any open orders and creating new ones if any have filled completely.
           We start from the closest orders outward."""

        tickLog = self.exchange.get_instrument()['tickLog']
        to_amend = []
        to_create = []
        to_cancel = []
        buys_matched = 0
        sells_matched = 0
        existing_orders = self.exchange.get_orders()
        quoting_side = settings.QUOTING_SIDE

        # Check all existing orders and match them up with what we want to place.
        # If there's an open one, we might be able to amend it to fit what we want.
        for order in existing_orders:
            try:
                if order['side'] == 'Buy':
                    desired_order = buy_orders[buys_matched]
                    buys_matched += 1
                else:
                    desired_order = sell_orders[sells_matched]
                    sells_matched += 1

                # Found an existing order. Do we need to amend it?
                if desired_order['orderQty'] != order['leavesQty'] or (
                        # If price has changed, and the change is more than our RELIST_INTERVAL, amend.
                        desired_order['price'] != order['price'] and
                        abs((desired_order['price'] / order['price']) - 1) > settings.RELIST_INTERVAL):
                    if self.is_order_placement_allowed(desired_order, quoting_side) is True:
                        to_amend.append({'orderID': order['orderID'], 'orderQty': order['cumQty'] + desired_order['orderQty'],
                                        'price': desired_order['price'], 'side': order['side']})
            except IndexError:
                # Will throw if there isn't a desired order to match. In that case, cancel it.
                to_cancel.append(order)

        while buys_matched < len(buy_orders):
            buy_order = buy_orders[buys_matched]
            if self.is_order_placement_allowed(buy_order, quoting_side):
                to_create.append(buy_order)
            buys_matched += 1

        while sells_matched < len(sell_orders):
            sell_order = sell_orders[sells_matched]
            if self.is_order_placement_allowed(sell_order, quoting_side):
                to_create.append(sell_order)
            sells_matched += 1

        if len(to_amend) > 0:
            combined_msg = ""
            for amended_order in reversed(to_amend):
                reference_order = [o for o in existing_orders if o['orderID'] == amended_order['orderID']][0]
                combined_msg += "Amending {:>4}: {} @ {} to {} @ {} ({})\n".format(
                    amended_order['side'], reference_order['leavesQty'], reference_order['price'],
                    (amended_order['orderQty'] - reference_order['cumQty']), amended_order['price'],
                    (amended_order['price'] - reference_order['price'])
                )
            log_info(self.logger, combined_msg, False)

            # This can fail if an order has closed in the time we were processing.
            # The API will send us `invalid ordStatus`, which means that the order's status (Filled/Canceled)
            # made it not amendable.
            # If that happens, we need to catch it and re-tick.
            try:
                self.exchange.amend_bulk_orders(to_amend)
            except requests.exceptions.HTTPError as e:
                errorObj = e.response.json()
                if errorObj['error']['message'] == 'Invalid ordStatus':
                    self.logger.warn("Amending failed. Waiting for order data to converge and retrying.")
                    sleep(0.5)
                    return self.place_orders()
                else:
                    log_error(self.logger, "Unknown error on amend: %s. Restarting" % errorObj, True)
                    raise ForceRestartException("NerdSupervisor will be restarted")

        if len(to_create) > 0:
            combined_msg = "Creating %d orders:\n" % (len(to_create))
            for order in reversed(to_create):
                combined_msg += "{:>4} {} @ {}\n".format(order['side'], order['orderQty'], order['price'])
            log_info(self.logger, combined_msg, False)

            self.print_status(True)

            self.exchange.create_bulk_orders(to_create)

        # Could happen if we exceed a delta limit
        if len(to_cancel) > 0:
            combined_msg = "Cancelling %d orders:\n" % (len(to_cancel))
            for order in reversed(to_cancel):
                combined_msg += "%4s %d @ %.*f\n" % (order['side'], order['leavesQty'], tickLog, order['price'])
            log_info(self.logger, combined_msg, False)
            self.exchange.cancel_bulk_orders(to_cancel)

    def get_ticker(self):
        instrument = self.exchange.get_instrument()
        ticker = self.exchange.get_ticker()
        tickSize = instrument['tickSize']
        tickLog = instrument['tickLog']

        # Set up our buy & sell positions as the smallest possible unit above and below the current spread
        # and we'll work out from there. That way we always have the best price but we don't kill wide
        # and potentially profitable spreads.
        self.start_position_buy = ticker["buy"] + tickSize
        self.start_position_sell = ticker["sell"] - tickSize

        # If we're maintaining spreads and we already have orders in place,
        # make sure they're not ours. If they are, we need to adjust, otherwise we'll
        # just work the orders inward until they collide.
        if settings.MAINTAIN_SPREADS:
            if ticker['buy'] == self.exchange.get_highest_buy()['price']:
                self.start_position_buy = ticker["buy"]
            if ticker['sell'] == self.exchange.get_lowest_sell()['price']:
                self.start_position_sell = ticker["sell"]

        # Back off if our spread is too small.
        if self.start_position_buy * (1.00 + settings.MIN_SPREAD) > self.start_position_sell:
            self.start_position_buy *= (1.00 - (settings.MIN_SPREAD / 2))
            self.start_position_sell *= (1.00 + (settings.MIN_SPREAD / 2))

        # Midpoint, used for simpler order placement.
        self.start_position_mid = ticker["mid"]
        self.logger.debug("{} Ticker: Buy: {}, Sell: {}".format(instrument['symbol'], round(ticker["buy"], tickLog), round(ticker["sell"], tickLog)))
        self.logger.debug('Start Positions: Buy: {}, Sell: {}, Mid: {}'.format(self.start_position_buy, self.start_position_sell, self.start_position_mid))
        return ticker

    ###
    # Sanity
    ##
    def sanity_check(self):
        """Perform checks before placing orders."""

        # Check if OB is empty - if so, can't quote.
        self.exchange.check_if_orderbook_empty()

        # Ensure market is still open.
        self.exchange.check_market_open()

        # Get ticker, which sets price offsets and prints some debugging info.
        ticker = self.get_ticker()

        # Sanity check:
        if self.get_price_offset(-1) >= ticker["sell"] or self.get_price_offset(1) <= ticker["buy"]:
            self.logger.error("Buy: {}, Sell: {}".format(self.start_position_buy, self.start_position_sell))
            self.logger.error("First buy position: {}\nBest Ask: {}\nFirst sell position: {}\nBest Bid: {}".format(self.get_price_offset(-1), ticker["sell"], self.get_price_offset(1), ticker["buy"]))
            log_error(self.logger, "Sanity check failed, exchange data is inconsistent", True)
            raise ForceRestartException("NerdSupervisor will be restarted")

        # Messaging if the position limits are reached
        if self.long_position_limit_exceeded():
            self.logger.debug("Long delta limit exceeded")
            self.logger.debug("Current Position: {}, Maximum Position: {}".format(self.exchange.get_delta(), settings.MAX_POSITION))

        if self.short_position_limit_exceeded():
            self.logger.debug("Short delta limit exceeded")
            self.logger.debug("Current Position: {}, Minimum Position: {}".format(self.exchange.get_delta(), settings.MIN_POSITION))
