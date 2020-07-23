from abc import abstractmethod
from market_maker.settings import settings
from market_maker.utils import mm_math
from market_maker.utils.log import log_debug
from market_maker.utils.log import log_info
from market_maker.utils.log import log_error
from market_maker.dynamic_settings import DynamicSettings
from market_maker.db.db_manager import DatabaseManager
from market_maker.db.quoting_side import *
from market_maker.db.market_regime import MarketRegime
from common.exception import *
import math


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

    def on_market_snapshot_update(self):
        robot_settings = DatabaseManager.retrieve_robot_settings(self.logger, settings.EXCHANGE, settings.ROBOTID)
        market_snapshot = DatabaseManager.retrieve_market_snapshot(self.logger, settings.EXCHANGE, settings.SYMBOL)
        if market_snapshot:
            self.logger.debug("on_market_snapshot_update(): self.market_snapshot={}".format(market_snapshot))
            prev_market_regime = self.curr_market_snapshot.marketregime if self.curr_market_snapshot else None
            prev_atr = self.curr_market_snapshot.atr_pct if self.curr_market_snapshot else "N/A"
            new_market_regime = market_snapshot.marketregime
            new_atr = market_snapshot.atr_pct
            is_atr_changed = prev_atr != new_atr and not math.isnan(new_atr)
            is_market_regime_changed = prev_market_regime != new_market_regime and not math.isnan(new_market_regime)
            if is_atr_changed or is_market_regime_changed:
                # log_info(logger, "Market Snapshot has been updated:\nATR (5 min): {} => {}\nMarket Regime: {} => {}".format(self.get_pct_value(prev_atr), self.get_pct_value(new_atr), MarketRegime.get_name(prev_market_regime), MarketRegime.get_name(new_market_regime)), True)
                self.curr_market_snapshot = market_snapshot

            if is_atr_changed:
                self.update_dynamic_app_settings(True)

            new_quoting_side = self.resolve_quoting_side(new_market_regime)
            robot_quoting_side = robot_settings.quoting_side
            running_qty = self.exchange.get_delta()
            if running_qty == 0 and new_quoting_side != robot_quoting_side:
                settings.QUOTING_SIDE = new_quoting_side
                DatabaseManager.update_robot_quoting_side(self.logger, settings.EXCHANGE, settings.ROBOTID, new_quoting_side)
                log_info(self.logger, "As {} has no open positions and quoting side has changed, setting the new quoting side={}".format(settings.ROBOTID, new_quoting_side), True)
                self.exchange.cancel_all_orders()

    @abstractmethod
    def check_suspend_trading(self):
        pass

    @abstractmethod
    def place_orders(self):
        pass

    @abstractmethod
    def prepare_order(self, index):
        pass

    @abstractmethod
    def prepare_tp_order(self, is_long, quantity):
        pass

    @abstractmethod
    def converge_orders(self, buy_orders, sell_orders):
        pass

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

    @abstractmethod
    def update_dynamic_app_settings(self, force_update):
        pass

    def resolve_quoting_side(self, market_regime):
        if market_regime == MarketRegime.BULLISH:
            return QuotingSide.LONG
        if market_regime == MarketRegime.BEARISH:
            return QuotingSide.SHORT
        if market_regime == MarketRegime.RANGE:
            return QuotingSide.BOTH

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

    @abstractmethod
    def get_ticker(self):
        pass

    @abstractmethod
    def sanity_check(self):
        pass

    def is_quoting_side_ok(self, is_long, quoting_side):
        result = None
        if is_long:
            result = quoting_side in [QuotingSide.BOTH, QuotingSide.LONG]
        else:
            result = quoting_side in [QuotingSide.BOTH, QuotingSide.SHORT]

        log_debug(self.logger, "is_quoting_side_ok(): is_long={}, result={}".format(is_long, result), False)
        return result

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

    def is_market_snapshot_initialized(self):
        return self.curr_market_snapshot.atr_pct != 0
