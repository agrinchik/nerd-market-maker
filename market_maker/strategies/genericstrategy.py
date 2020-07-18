from abc import abstractmethod
from market_maker.settings import settings
from market_maker.utils import mm_math
from market_maker.utils.log import log_debug
from market_maker.utils.log import log_info
from market_maker.utils.log import log_error
from market_maker.dynamic_settings import DynamicSettings
from market_maker.db.quoting_side import *
from market_maker.db.market_regime import MarketRegime
from common.exception import *



class GenericStrategy(object):

    def __init__(self, logger, exchange):
        self.logger = logger
        self.exchange = exchange
        self.start_position_buy = 0
        self.start_position_sell = 0
        self.start_position_mid = 0
        self.curr_market_snapshot = None
        self.is_trading_suspended = False
        self.starting_qty = self.exchange.get_delta()
        self.running_qty = self.starting_qty
        self.dynamic_settings = DynamicSettings(self.exchange)

    @abstractmethod
    def on_market_snapshot_update(self):
        pass

    def update_dynamic_app_settings(self, force_update):
        result = self.dynamic_settings.update_app_settings(self.curr_market_snapshot, force_update)

        if result:
            self.exchange.cancel_all_orders()

    def resolve_quoting_side(self, market_regime):
        if market_regime == MarketRegime.BULLISH:
            return QuotingSide.LONG
        if market_regime == MarketRegime.BEARISH:
            return QuotingSide.SHORT
        if market_regime == MarketRegime.RANGE:
            return QuotingSide.BOTH

    def get_price_offset(self, index):
        instrument = self.exchange.get_instrument()
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

        return mm_math.toNearest(start_position * (1 + settings.INTERVAL) ** index, instrument['tickSize'])

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

    def get_deposit_usage_pct(self, running_qty):
        if running_qty < 0:
            return abs(running_qty / settings.MIN_POSITION) * 100
        else:
            return abs(running_qty / settings.MAX_POSITION) * 100

    def get_pct_value(self, val):
        return "{}%".format(round(val * 100, 2))

    def print_status(self, send_to_telegram):
        """Print the current status of NerdMarkerMakerRobot"""

        margin = self.exchange.get_margin()
        position = self.exchange.get_position()
        running_qty = self.exchange.get_delta()
        wallet_balance = margin["walletBalance"]
        instrument = self.exchange.get_instrument(position["symbol"])
        tick_log = instrument["tickLog"]
        last_price = self.get_ticker()["last"]

        combined_msg = "Wallet Balance: {}\n".format(mm_math.get_round_value(wallet_balance, 8))
        combined_msg += "Last Price: {}\n".format(mm_math.get_round_value(last_price, 8))
        combined_msg += "Position: {} ({}%)\n".format(mm_math.get_round_value(running_qty, tick_log), round(self.get_deposit_usage_pct(running_qty), 2))
        if position['currentQty'] != 0:
            combined_msg += "Avg Entry Price: {}\n".format(mm_math.get_round_value(position['avgEntryPrice'], tick_log))
            combined_msg += "Distance To Avg Price: {:.2f}%\n".format(self.exchange.get_distance_to_avg_price_pct())
            combined_msg += "Unrealized PnL: {:.8f} ({:.2f}%)\n".format(mm_math.get_round_value(self.exchange.get_unrealized_pnl(), tick_log), self.exchange.get_unrealized_pnl_pct())
            combined_msg += "Liquidation Price (Dist %): {} ({:.2f}%)\n".format(mm_math.get_round_value(float(position['liquidationPrice']), tick_log), self.exchange.get_distance_to_liq_price_pct())
        combined_msg += "ATR (5 min) = {}\n".format(self.get_pct_value(self.curr_market_snapshot.atr_pct)) if self.curr_market_snapshot else "N/A"
        combined_msg += "Interval, % (RP) = {} ({})\n".format(self.get_pct_value(self.dynamic_settings.interval_pct), self.dynamic_settings.curr_risk_profile_id)
        combined_msg += "Min/Max Position = {}/{}\n".format(self.dynamic_settings.min_position, self.dynamic_settings.max_position)
        combined_msg += "Lot Size = {}\n".format(self.dynamic_settings.order_start_size)
        combined_msg += "Quoting Side = {}\n".format(settings.QUOTING_SIDE)
        log_debug(self.logger, combined_msg, send_to_telegram)