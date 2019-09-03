from __future__ import absolute_import
from time import sleep
import sys
import datetime
from datetime import datetime
from os.path import getmtime
import random
import requests
import atexit
import signal
from market_maker.utils.bitmex.log import log_info
from market_maker.utils.bitmex.log import log_error

from market_maker import bitmex
from market_maker import bitfinex
from market_maker.settings import settings
from market_maker.utils.bitmex import constants, errors, log, math

from market_maker.dynamic_settings import DynamicSettings

from market_maker.utils.bitmex.utils import XBt_to_XBT

# Used for reloading the bot - saves modified times of key files
watched_files_mtimes = [(f, getmtime(f)) for f in settings.WATCHED_FILES]


#
# Helpers
#
logger = log.setup_custom_logger('root')


class ForceRestartException(Exception):
    pass


class ExchangeInterface:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.symbol = settings.SYMBOL
        '''self.xchange = bitmex.BitMEX(base_url=settings.BASE_URL, symbol=self.symbol,
                                    apiKey=settings.API_KEY, apiSecret=settings.API_SECRET,
                                    orderIDPrefix=settings.ORDERID_PREFIX, postOnly=settings.POST_ONLY,
                                    timeout=settings.TIMEOUT,
                                    retries=settings.RETRIES,
                                    retry_delay=settings.RETRY_DELAY
                                    )'''
        self.xchange = bitfinex.Bitfinex(symbol=self.symbol)

    def cancel_all_orders(self):
        if self.dry_run:
            return

        logger.info("Resetting current position. Canceling all existing orders.")
        tickLog = self.get_instrument()['tickLog']

        # In certain cases, a WS update might not make it through before we call this.
        # For that reason, we grab via HTTP to ensure we grab them all.
        orders = self.xchange.http_open_orders()

        for order in orders:
            logger.info("Canceling: %s %d @ %.*f" % (order['side'], order['orderQty'], tickLog, order['price']))

        if len(orders):
            self.xchange.cancel([order['orderID'] for order in orders])

        sleep(settings.API_REST_INTERVAL)

    def get_delta(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.get_position(symbol)['currentQty']

    def get_instrument(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.xchange.instrument(symbol)

    def get_distance_to_avg_price_pct(self):
        result = 0
        position = self.get_position()
        last_price = self.get_ticker()["last"]
        if position['currentQty'] != 0:
            result = round(-(last_price - position['avgEntryPrice']) * 100 / last_price, 2)
        return result

    def get_distance_to_liq_price_pct(self):
        result = 0
        position = self.get_position()
        last_price = self.get_ticker()["last"]
        if position['currentQty'] != 0:
            result = abs(round((last_price - position['liquidationPrice']) * 100 / last_price, 2))
        return result

    def get_position_pnl_text_status(self):
        result = ""
        position = self.get_position()
        last_price = self.get_ticker()["last"]
        curr_quantity = position['currentQty']
        avg_entry_price = position['avgEntryPrice']
        if curr_quantity != 0:
            if curr_quantity > 0 and last_price >= avg_entry_price:
                result = "GAIN"
            elif curr_quantity > 0 and last_price < avg_entry_price:
                result = "LOSS"
            elif curr_quantity < 0 and last_price >= avg_entry_price:
                result = "LOSS"
            elif curr_quantity < 0 and last_price < avg_entry_price:
                result = "GAIN"
        return result


    def get_margin(self):
        if self.dry_run:
            return {'marginBalance': float(settings.DRY_BTC), 'availableFunds': float(settings.DRY_BTC)}
        return self.xchange.funds()

    def get_orders(self):
        if self.dry_run:
            return []
        return self.xchange.open_orders()

    def get_highest_buy(self):
        buys = [o for o in self.get_orders() if o['side'] == 'Buy']
        if not len(buys):
            return {'price': -2**32}
        highest_buy = max(buys or [], key=lambda o: o['price'])
        return highest_buy if highest_buy else {'price': -2**32}

    def get_lowest_sell(self):
        sells = [o for o in self.get_orders() if o['side'] == 'Sell']
        if not len(sells):
            return {'price': 2**32}
        lowest_sell = min(sells or [], key=lambda o: o['price'])
        return lowest_sell if lowest_sell else {'price': 2**32}  # ought to be enough for anyone

    def get_position(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.xchange.position(symbol)

    def get_ticker(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.xchange.ticker_data(symbol)

    def is_open(self):
        """Check that websockets are still open."""
        return not self.xchange.ws.exited

    def check_market_open(self):
        instrument = self.get_instrument()
        if instrument["state"] != "Open" and instrument["state"] != "Closed":
            raise errors.MarketClosedError("The instrument %s is not open. State: %s" %
                                           (self.symbol, instrument["state"]))

    def check_if_orderbook_empty(self):
        """This function checks whether the order book is empty"""
        instrument = self.get_instrument()
        if instrument['midPrice'] is None:
            raise errors.MarketEmptyError("Orderbook is empty, cannot quote")

    def amend_bulk_orders(self, orders):
        if self.dry_run:
            return orders
        return self.xchange.amend_bulk_orders(orders)

    def create_bulk_orders(self, orders):
        if self.dry_run:
            return orders
        return self.xchange.create_bulk_orders(orders)

    def cancel_bulk_orders(self, orders):
        if self.dry_run:
            return orders
        return self.xchange.cancel([order['orderID'] for order in orders])


class OrderManager:
    def __init__(self):
        self.exchange = ExchangeInterface(settings.DRY_RUN)
        # Once exchange is created, register exit handler that will always cancel orders
        # on any error.
        atexit.register(self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        logger.info("Using symbol %s." % self.exchange.symbol)

        if settings.DRY_RUN:
            logger.info("Initializing dry run. Orders printed below represent what would be posted to BitMEX.")
        else:
            logger.info("Order Manager initializing, connecting to BitMEX. Live run: executing real trades.")

        self.start_time = datetime.now()
        self.instrument = self.exchange.get_instrument()
        self.starting_qty = self.exchange.get_delta()
        self.running_qty = self.starting_qty
        self.max_wallet_balance = self.get_cached_wallet_balance()
        self.dynamic_settings = DynamicSettings(self.exchange)
        self.is_trading_suspended = False
        self.price_change_last_check = datetime.now()
        self.price_change_last_price = -1
        self.reset()

    def get_wallet_balance_filename(self):
        if settings.ENV == "TEST":
            return "./stats/walletbalance/test.txt"
        else:
            return "./stats/walletbalance/live.txt"

    def get_cached_wallet_balance(self):
        result = 0
        filename = self.get_wallet_balance_filename()
        with open(filename, encoding='utf8') as f:
            text = f.read().strip()
            result = float(text)
        return result

    def get_deposit_load_pct(self, running_qty):
        if running_qty < 0:
            return abs(running_qty / settings.MIN_POSITION) * 100
        else:
            return abs(running_qty / settings.MAX_POSITION) * 100

    def store_wallet_balance(self, balance):
        filename = self.get_wallet_balance_filename()
        with open(filename, "w") as text_file:
            text_file.write("{:08}".format(balance))

    def reset(self):
        self.exchange.cancel_all_orders()
        self.sanity_check()
        self.print_status(False)
        self.check_suspend_trading()
        self.check_stop_trading()
        self.dynamic_settings.initialize_params()

        # Create orders and converge.
        self.place_orders()

    def print_status(self, send_to_telegram):
        """Print the current MM status."""

        margin = self.exchange.get_margin()
        position = self.exchange.get_position()
        ticker = self.exchange.get_ticker()
        last_price = ticker["last"]
        self.running_qty = self.exchange.get_delta()
        tickLog = self.exchange.get_instrument()['tickLog']
        wallet_balance_XBT = XBt_to_XBT(margin["walletBalance"])
        wallet_balance_USD = wallet_balance_XBT * last_price
        self.start_XBt = margin["marginBalance"]

        combined_msg = "\nWallet Balance: %.8f ($%.2f)\n" % (wallet_balance_XBT, wallet_balance_USD)
        combined_msg += "Margin Balance: %.8f\n" % XBt_to_XBT(self.start_XBt)
        combined_msg += "Contract Position: {} ({}%)\n".format(self.running_qty, round(self.get_deposit_load_pct(self.running_qty), 2))
        if settings.CHECK_POSITION_LIMITS:
            combined_msg += "Position limits: %d/%d\n" % (settings.MIN_POSITION, settings.MAX_POSITION)
        if position['currentQty'] != 0:
            combined_msg += "Avg Entry Price: %.*f\n" % (tickLog, float(position['avgEntryPrice']))
            combined_msg += "Distance To Avg Price: {:.2f}% ({})\n".format(self.exchange.get_distance_to_avg_price_pct(), self.exchange.get_position_pnl_text_status())
            combined_msg += "Liquidation Price: %.*f\n" % (tickLog, float(position['liquidationPrice']))
            combined_msg += "Distance To Liq. Price: {:.2f}%\n".format(self.exchange.get_distance_to_liq_price_pct())
        log_info(logger, combined_msg, send_to_telegram)

    def check_suspend_trading(self):
        curr_time = datetime.now()
        ticker = self.exchange.get_ticker()
        ticker_last_price = ticker["last"]
        price_change_last_checked_seconds_ago = (curr_time - self.price_change_last_check).total_seconds()
        price_change_diff_pct = abs((ticker_last_price - self.price_change_last_price) * 100 / self.price_change_last_price)

        if self.is_trading_suspended is False:
            if settings.STOP_QUOTING_CHECK_IMPULSE_PRICE_CHANGE is True:
                if self.price_change_last_price == -1:
                    self.price_change_last_check = curr_time
                    self.price_change_last_price = ticker_last_price
                    return

                if price_change_last_checked_seconds_ago > settings.STOP_QUOTING_PRICE_CHANGE_CHECK_TIME_PERIOD_SECONDS:
                    if price_change_diff_pct > settings.STOP_QUOTING_PRICE_CHANGE_EXCEEDED_THRESHOLD_PCT:
                        log_info(logger, "WARNING: Trading would be SUSPENDED as in the past {} seconds the XBT last price had moved very fast and exceeded the threshold = {}%".
                                 format(settings.STOP_QUOTING_PRICE_CHANGE_CHECK_TIME_PERIOD_SECONDS, settings.STOP_QUOTING_PRICE_CHANGE_EXCEEDED_THRESHOLD_PCT), True)
                        self.is_trading_suspended = True
                        self.exchange.cancel_all_orders()
                    self.price_change_last_check = curr_time
                    self.price_change_last_price = ticker_last_price
        else:
            if settings.STOP_QUOTING_CHECK_IMPULSE_PRICE_CHANGE is True:
                if price_change_last_checked_seconds_ago > settings.STOP_QUOTING_PRICE_CHANGE_CHECK_TIME_PERIOD_SECONDS:
                    if price_change_diff_pct < settings.RESUME_QUOTING_PRICE_CHANGE_WENT_BELOW_THRESHOLD_PCT:
                        log_info(logger, "WARNING: Trading would be RESUMED as in the past {} seconds the XBT last price had changed within the threshold = {}%".
                                 format(settings.STOP_QUOTING_PRICE_CHANGE_CHECK_TIME_PERIOD_SECONDS, settings.RESUME_QUOTING_PRICE_CHANGE_WENT_BELOW_THRESHOLD_PCT), True)
                        self.is_trading_suspended = False
                    self.price_change_last_check = curr_time
                    self.price_change_last_price = ticker_last_price

    def check_stop_trading(self):
        margin = self.exchange.get_margin()
        curr_wallet_balance = XBt_to_XBT(margin["walletBalance"])
        cached_wallet_balance = self.get_cached_wallet_balance()
        capital_drawdown_pct = abs(100 * (curr_wallet_balance - cached_wallet_balance) / cached_wallet_balance)
        if curr_wallet_balance > cached_wallet_balance:
            self.store_wallet_balance(curr_wallet_balance)
        elif capital_drawdown_pct > settings.STOP_TRADING_CAPITAL_STOPLOSS_PCT:
            log_info(logger, "CRITICAL: current wallet balance drawdown has exceeded capital stop-loss value ({}%)! Shutting down the NerdMarketMaker!".format(settings.STOP_TRADING_CAPITAL_STOPLOSS_PCT), True)
            self.exit(settings.STOP_TRADING_CAPITAL_STOPLOSS_EXIT_STATUS_CODE)

    def get_ticker(self):
        ticker = self.exchange.get_ticker()
        tickLog = self.exchange.get_instrument()['tickLog']

        # Set up our buy & sell positions as the smallest possible unit above and below the current spread
        # and we'll work out from there. That way we always have the best price but we don't kill wide
        # and potentially profitable spreads.
        self.start_position_buy = ticker["buy"] + self.instrument['tickSize']
        self.start_position_sell = ticker["sell"] - self.instrument['tickSize']

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
        logger.info(
            "%s Ticker: Buy: %.*f, Sell: %.*f" %
            (self.instrument['symbol'], tickLog, ticker["buy"], tickLog, ticker["sell"])
        )
        logger.info('Start Positions: Buy: %.*f, Sell: %.*f, Mid: %.*f' %
                    (tickLog, self.start_position_buy, tickLog, self.start_position_sell,
                     tickLog, self.start_position_mid))
        return ticker

    def get_price_offset(self, index):
        """Given an index (1, -1, 2, -2, etc.) return the price for that side of the book.
           Negative is a buy, positive is a sell."""
        # Maintain existing spreads for max profit
        if settings.MAINTAIN_SPREADS:
            start_position = self.start_position_buy if index < 0 else self.start_position_sell
            # First positions (index 1, -1) should start right at start_position, others should branch from there
            index = index + 1 if index < 0 else index - 1
        else:
            # Offset mode: ticker comes from a reference exchange and we define an offset.
            start_position = self.start_position_buy if index < 0 else self.start_position_sell

            # If we're attempting to sell, but our sell price is actually lower than the buy,
            # move over to the sell side.
            if index > 0 and start_position < self.start_position_buy:
                start_position = self.start_position_sell
            # Same for buys.
            if index < 0 and start_position > self.start_position_sell:
                start_position = self.start_position_buy

        return math.toNearest(start_position * (1 + settings.INTERVAL) ** index, self.instrument['tickSize'])

    ###
    # Orders
    ###

    def place_orders(self):
        """Create order items for use in convergence."""

        buy_orders = []
        sell_orders = []

        self.running_qty = self.exchange.get_delta()
        if settings.WORKING_MODE == settings.MODE2_ALWAYS_CLOSE_FULL_POSITION_STRATEGY and self.running_qty != 0:
            if self.running_qty > 0:
                sell_orders.append(self.prepare_order_opposite_side(True, abs(self.running_qty)))
                for i in reversed(range(1, settings.ORDER_PAIRS + 1)):
                    if not self.long_position_limit_exceeded():
                        buy_orders.append(self.prepare_order(-i))
            else:
                buy_orders.append(self.prepare_order_opposite_side(False, abs(self.running_qty)))
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

        if settings.RANDOM_ORDER_SIZE is True:
            quantity = random.randint(settings.MIN_ORDER_SIZE, settings.MAX_ORDER_SIZE)
        else:
            quantity = settings.ORDER_START_SIZE + ((abs(index) - 1) * settings.ORDER_STEP_SIZE)

        price = self.get_price_offset(index)

        return {'price': price, 'orderQty': quantity, 'side': "Buy" if index < 0 else "Sell"}

    def prepare_order_opposite_side(self, is_long, quantity):
        position = self.exchange.get_position()
        avg_entry_price = position['avgEntryPrice']
        take_profit_pct = settings.MODE2_CLOSE_FULL_POSITION_TAKE_PROFIT_PCT
        if is_long:
            price = avg_entry_price + avg_entry_price * take_profit_pct
        else:
            price = avg_entry_price - avg_entry_price * take_profit_pct
        price = math.toNearest(price, self.instrument['tickSize'])

        return {'price': price, 'orderQty': quantity, 'side': "Sell" if is_long is True else "Buy"}

    def is_order_placement_allowed(self, order):
        result = True
        position = self.exchange.get_position()
        position_avg_price = position['avgEntryPrice']
        position_qty = position['currentQty']
        is_order_buy_side = True if order["side"] == "Buy" else False
        order_price = order["price"]

        if settings.STOP_QUOTING_IF_INSIDE_LOSS_RANGE is False or position_qty == 0:
            result = True
        else:
            if position_qty > 0:
                if is_order_buy_side is True:
                    result = True
                else:
                    if order_price >= position_avg_price:
                        result = True
                    else:
                        result = False
            else:
                if is_order_buy_side is False:
                    result = True
                else:
                    if order_price <= position_avg_price:
                        result = True
                    else:
                        result = False

        log_info(logger, "is_order_placement_allowed(): order={}, result={}".format(order, result), False)
        return result

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
                    if self.is_order_placement_allowed(desired_order) is True:
                        to_amend.append({'orderID': order['orderID'], 'orderQty': order['cumQty'] + desired_order['orderQty'],
                                        'price': desired_order['price'], 'side': order['side']})
            except IndexError:
                # Will throw if there isn't a desired order to match. In that case, cancel it.
                to_cancel.append(order)

        while buys_matched < len(buy_orders):
            buy_order = buy_orders[buys_matched]
            if self.is_order_placement_allowed(buy_order) is True:
                to_create.append(buy_order)
            buys_matched += 1

        while sells_matched < len(sell_orders):
            sell_order = sell_orders[sells_matched]
            if self.is_order_placement_allowed(sell_order) is True:
                to_create.append(sell_order)
            sells_matched += 1

        if len(to_amend) > 0:
            combined_msg = ""
            for amended_order in reversed(to_amend):
                reference_order = [o for o in existing_orders if o['orderID'] == amended_order['orderID']][0]
                combined_msg += "Amending %4s: %d @ %.*f to %d @ %.*f (%+.*f)\n" % (
                    amended_order['side'],
                    reference_order['leavesQty'], tickLog, reference_order['price'],
                    (amended_order['orderQty'] - reference_order['cumQty']), tickLog, amended_order['price'],
                    tickLog, (amended_order['price'] - reference_order['price'])
                )
            log_info(logger, combined_msg, False)

            # This can fail if an order has closed in the time we were processing.
            # The API will send us `invalid ordStatus`, which means that the order's status (Filled/Canceled)
            # made it not amendable.
            # If that happens, we need to catch it and re-tick.
            try:
                self.exchange.amend_bulk_orders(to_amend)
            except requests.exceptions.HTTPError as e:
                errorObj = e.response.json()
                if errorObj['error']['message'] == 'Invalid ordStatus':
                    logger.warn("Amending failed. Waiting for order data to converge and retrying.")
                    sleep(0.5)
                    return self.place_orders()
                else:
                    log_error(logger, "Unknown error on amend: %s. Exiting" % errorObj, True)
                    sys.exit(1)

        if len(to_create) > 0:
            combined_msg = "Creating %d orders:\n" % (len(to_create))
            for order in reversed(to_create):
                combined_msg += "%4s %d @ %.*f\n" % (order['side'], order['orderQty'], tickLog, order['price'])
            log_info(logger, combined_msg, False)

            self.print_status(True)

            self.exchange.create_bulk_orders(to_create)

        # Could happen if we exceed a delta limit
        if len(to_cancel) > 0:
            combined_msg = "Cancelling %d orders:\n" % (len(to_cancel))
            for order in reversed(to_cancel):
                combined_msg += "%4s %d @ %.*f\n" % (order['side'], order['leavesQty'], tickLog, order['price'])
            log_info(logger, combined_msg, False)
            self.exchange.cancel_bulk_orders(to_cancel)

    ###
    # Position Limits
    ###

    def short_position_limit_exceeded(self):
        """Returns True if the short position limit is exceeded"""
        if not settings.CHECK_POSITION_LIMITS:
            return False
        position = self.exchange.get_delta()
        return position <= settings.MIN_POSITION

    def long_position_limit_exceeded(self):
        """Returns True if the long position limit is exceeded"""
        if not settings.CHECK_POSITION_LIMITS:
            return False
        position = self.exchange.get_delta()
        return position >= settings.MAX_POSITION

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
            logger.error("Buy: %s, Sell: %s" % (self.start_position_buy, self.start_position_sell))
            logger.error("First buy position: %s\nBitMEX Best Ask: %s\nFirst sell position: %s\nBitMEX Best Bid: %s" %
                         (self.get_price_offset(-1), ticker["sell"], self.get_price_offset(1), ticker["buy"]))
            log_error(logger, "Sanity check failed, exchange data is inconsistent", True)
            self.exit()

        # Messaging if the position limits are reached
        if self.long_position_limit_exceeded():
            logger.info("Long delta limit exceeded")
            logger.info("Current Position: %.f, Maximum Position: %.f" %
                        (self.exchange.get_delta(), settings.MAX_POSITION))

        if self.short_position_limit_exceeded():
            logger.info("Short delta limit exceeded")
            logger.info("Current Position: %.f, Minimum Position: %.f" %
                        (self.exchange.get_delta(), settings.MIN_POSITION))

    ###
    # Running
    ###

    def update_app_settings(self):
        result = self.dynamic_settings.update_app_settings()
        if result is True:
            self.exchange.cancel_all_orders()

    def check_connection(self):
        """Ensure the WS connections are still open."""
        return self.exchange.is_open()

    def exit(self, status=None):
        logger.info("Shutting down. All open orders will be cancelled.")
        try:
            self.exchange.cancel_all_orders()
            self.exchange.xchange.exit()
        except errors.AuthenticationError as e:
            logger.info("Was not authenticated; could not cancel orders.")
        except Exception as e:
            logger.info("Unable to cancel orders: %s" % e)

        sys.exit(status)

    def run_loop(self):
        while True:
            logger.info("*" * 400)

            sleep(settings.LOOP_INTERVAL)

            # This will restart on very short downtime, but if it's longer,
            # the MM will crash entirely as it is unable to connect to the WS on boot.
            if not self.check_connection():
                RESTART_TIMEOUT = 60
                log_error(logger, "Realtime data connection unexpectedly closed, restarting in {} seconds.".format(RESTART_TIMEOUT), True)
                sleep(RESTART_TIMEOUT)
                self.restart()

            self.sanity_check()  # Ensures health of mm - several cut-out points here
            self.print_status(False)  # Print skew, delta, etc
            self.check_suspend_trading()
            self.check_stop_trading()
            self.dynamic_settings.update_app_settings()
            self.place_orders()  # Creates desired orders and converges to existing orders

    def restart(self):
        logger.info("Restarting the market maker...")
        #os.execv(sys.executable, [sys.executable] + sys.argv)
        raise ForceRestartException("The NerdMarketMaker bot will be restarted")


def run():
    log_info(logger, 'Nerd Market Maker %s\n' % constants.VERSION, True)

    om = OrderManager()
    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        om.run_loop()
    except (ForceRestartException, KeyboardInterrupt) as fe:
        sys.exit(1)
    except SystemExit as se:
        sys.exit(se.code)
    except Exception as e:
        log_error(logger, "Unexpected exception! {}".format(e), True)
