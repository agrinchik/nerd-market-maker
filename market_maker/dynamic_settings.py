
import logging
from market_maker.utils.utils import XBt_to_XBT
import datetime
from datetime import timedelta
from market_maker.utils.log import log_info
from market_maker.settings import settings

DEFAULT_POSITION_MARGIN_TO_WALLET_RATIO_PCT = 0.0386
DEFAULT_ORDER_MARGIN_TO_WALLET_RATIO_PCT = 0.0386
DEFAULT_LEVERAGE = 100
DEFAULT_INITIAL_MARGIN_BASE_PCT = 0.01
DEFAULT_TAKER_FEE_PCT = 0.00075
DEFAULT_MIN_SPREAD_ADJUSTMENT_FACTOR = 0.6
DEFAULT_RELIST_INTERVAL_ADJUSTMENT_FACTOR = 1.2
DEFAULT_MIN_POSITION_SHORTS_ADJUSTMENT_FACTOR = 1.4

BALANCE_BASED_PARAMS_UPDATE_INTERVAL = 1800    # 30 minutes
VOLATILITY_BASED_PARAMS_UPDATE_INTERVAL = 300  # 5 minutes

BALANCE_CHANGE_THRESHOLD_PCT = 0.01

# Pre-configured parameters based on volatility bands (BitMEX index - .BVOL24H)
VOLATILITY_BASED_PARAMS_ARR = [
    {
        "band_id": 0,
        "band_start": 0,
        "band_end": 2.999,
        "max_drawdown_pct": 0.075,
        "working_range_pct": 0.03,
        "max_number_dca_orders": 26,
    },
    {
        "band_id": 1,
        "band_start": 3,
        "band_end": 6.999,
        "max_drawdown_pct": 0.15,
        "working_range_pct": 0.06,
        "max_number_dca_orders": 26,
    },
    {
        "band_id": 2,
        "band_start": 7,
        "band_end": 99999999,
        "max_drawdown_pct": 0.30,
        "working_range_pct": 0.12,
        "max_number_dca_orders": 26,
    }
]


class DynamicSettings(object):

    def __init__(self, exchange):
        self.logger = logging.getLogger('root')
        self.exchange = exchange

        self.position_margin_pct = DEFAULT_POSITION_MARGIN_TO_WALLET_RATIO_PCT
        self.order_margin_pct = DEFAULT_ORDER_MARGIN_TO_WALLET_RATIO_PCT
        self.position_margin_amount = 0
        self.order_margin_amount = 0
        self.default_leverage = DEFAULT_LEVERAGE
        self.initial_margin_base_pct = DEFAULT_INITIAL_MARGIN_BASE_PCT
        self.taker_fee_pct = DEFAULT_TAKER_FEE_PCT
        self.max_possible_position_margin = 0
        self.max_drawdown_pct = 0
        self.working_range_pct = 0
        self.max_number_dca_orders = 0
        self.interval_pct = 0
        self.min_spread_pct = 0
        self.relist_interval_pct = 0
        self.min_position = 0
        self.max_position = 0
        self.order_step_size = 0
        self.order_start_size = 0
        self.order_pairs = 0

        self.balance_based_params_last_update = datetime.datetime.now() - timedelta(days=1000)
        self.curr_balance_value = 0
        self.volatility_based_params_last_update = datetime.datetime.now() - timedelta(days=1000)
        self.curr_volatility_band_id = -1

    def update_settings_value(self, key, value):
        if settings[key] != value:
            settings[key] = value

    def update_app_settings(self):
        params_updated = self.update_parameters()
        if params_updated is True:
            # TODO: Workaround - needs to be reimplemented
            self.update_settings_value("ORDER_PAIRS", self.order_pairs)
            self.update_settings_value("ORDER_START_SIZE", self.order_start_size)
            self.update_settings_value("ORDER_STEP_SIZE", self.order_step_size)
            self.update_settings_value("INTERVAL", self.interval_pct)
            self.update_settings_value("MIN_SPREAD", self.min_spread_pct)
            self.update_settings_value("RELIST_INTERVAL", self.relist_interval_pct)
            self.update_settings_value("MIN_POSITION", self.min_position)
            self.update_settings_value("MAX_POSITION", self.max_position)
            log_info(self.logger, "Updated NerdMarketMaker settings!", False)
        return params_updated

    def update_parameters(self):
        result = False
        ticker = self.exchange.get_ticker()
        ticker_last_price = ticker["last"]
        margin = self.exchange.get_margin()
        wallet_balance_XBT = XBt_to_XBT(margin["walletBalance"])
        curr_volatility = self.exchange.get_volatility()

        curr_time = datetime.datetime.now()
        volatility_based_params_seconds_from_last_update = (curr_time - self.volatility_based_params_last_update).total_seconds()
        volatility_band = self.get_volatility_band(curr_volatility)
        if volatility_based_params_seconds_from_last_update >= VOLATILITY_BASED_PARAMS_UPDATE_INTERVAL and volatility_band["band_id"] != self.curr_volatility_band_id:
            self.update_volatility_based_params(volatility_band)
            self.volatility_based_params_last_update = curr_time
            log_info(self.logger, "Updated volatility-based parameters!", True)
            result = True

        balance_based_params_seconds_from_last_update = (curr_time - self.balance_based_params_last_update).total_seconds()
        balance_change_pct = abs((wallet_balance_XBT - self.curr_balance_value) / self.curr_balance_value) if self.curr_balance_value != 0 else 1
        if balance_based_params_seconds_from_last_update >= BALANCE_BASED_PARAMS_UPDATE_INTERVAL and balance_change_pct >= BALANCE_CHANGE_THRESHOLD_PCT:
            self.update_balance_based_params(wallet_balance_XBT, ticker_last_price)
            self.balance_based_params_last_update = curr_time
            log_info(self.logger, "Updated balance-based parameters!", True)
            result = True

        if result is True:
            self.log_params()

        return result

    def update_balance_based_params(self, last_wallet_balance, ticker_last_price):
        self.curr_balance_value = last_wallet_balance
        self.position_margin_amount = round(last_wallet_balance * self.position_margin_pct, 8)
        self.order_margin_amount = round(last_wallet_balance * self.order_margin_pct, 8)
        self.max_possible_position_margin = round(self.position_margin_amount * self.default_leverage * ticker_last_price)
        self.min_position = round(-1 * self.max_possible_position_margin * DEFAULT_MIN_POSITION_SHORTS_ADJUSTMENT_FACTOR)
        self.max_position = round(self.max_possible_position_margin)
        self.order_step_size = self.get_order_step_size(last_wallet_balance)
        self.order_start_size = round(self.max_possible_position_margin / self.max_number_dca_orders - self.order_step_size * (self.max_number_dca_orders - 1) / 2)

    def update_volatility_based_params(self, volatility_band):
        self.populate_volatility_based_parameters(volatility_band)
        self.interval_pct = round(self.max_drawdown_pct / self.max_number_dca_orders, 8)
        self.min_spread_pct = round(self.interval_pct * 2 * DEFAULT_MIN_SPREAD_ADJUSTMENT_FACTOR, 8)
        self.relist_interval_pct = round(self.interval_pct * DEFAULT_RELIST_INTERVAL_ADJUSTMENT_FACTOR, 8)
        self.order_start_size = round(self.max_possible_position_margin / self.max_number_dca_orders - self.order_step_size * (self.max_number_dca_orders - 1) / 2)
        self.order_pairs = int(round(self.working_range_pct / self.interval_pct))

    def get_volatility_band(self, volatility24h):
        for entry in VOLATILITY_BASED_PARAMS_ARR:
            band_start = entry["band_start"]
            band_end = entry["band_end"]
            if volatility24h >= band_start and volatility24h <= band_end:
                return entry

        raise Exception("Unable to configure volatility-based parameters for volatility: " + volatility24h)

    def populate_volatility_based_parameters(self, volatility_band):
        self.curr_volatility_band_id = volatility_band["band_id"]
        self.max_drawdown_pct = volatility_band["max_drawdown_pct"]
        self.working_range_pct = volatility_band["working_range_pct"]
        self.max_number_dca_orders = volatility_band["max_number_dca_orders"]

    def get_order_step_size(self, last_wallet_balance):
        if last_wallet_balance < 0.2:
            return 0
        else:
            # TODO: Reimplement later
            return 0

    def append_log_text(self, str, txt):
        return str + txt + "\n"

    def get_pct_value(self, val):
        return "{}%".format(round(val * 100, 2))

    def log_params(self):
        txt = self.append_log_text("",  "Current parameters:")
        #txt = self.append_log_text(txt, "position_margin_pct = {}".format(self.get_pct_value(self.position_margin_pct)))
        #txt = self.append_log_text(txt, "order_margin_pct = {}".format(self.get_pct_value(self.order_margin_pct)))
        #txt = self.append_log_text(txt, "position_margin_amount = {}".format(self.position_margin_amount))
        #txt = self.append_log_text(txt, "order_margin_amount = {}".format(self.order_margin_amount))
        #txt = self.append_log_text(txt, "default_leverage = {}".format(self.default_leverage))
        #txt = self.append_log_text(txt, "initial_margin_base_pct = {}".format(self.get_pct_value(self.initial_margin_base_pct)))
        #txt = self.append_log_text(txt, "taker_fee_pct = {}".format(self.get_pct_value(self.taker_fee_pct)))
        txt = self.append_log_text(txt, "max_possible_position_margin = {}".format(self.max_possible_position_margin))
        txt = self.append_log_text(txt, "max_drawdown_pct = {}".format(self.get_pct_value(self.max_drawdown_pct)))
        txt = self.append_log_text(txt, "working_range_pct = {}".format(self.get_pct_value(self.working_range_pct)))
        txt = self.append_log_text(txt, "max_number_dca_orders = {}".format(self.max_number_dca_orders))
        txt = self.append_log_text(txt, "interval_pct = {}".format(self.get_pct_value(self.interval_pct)))
        txt = self.append_log_text(txt, "min_spread_pct = {}".format(self.get_pct_value(self.min_spread_pct)))
        txt = self.append_log_text(txt, "relist_interval_pct = {}".format(self.get_pct_value(self.relist_interval_pct)))
        txt = self.append_log_text(txt, "min_position = {}".format(self.min_position))
        txt = self.append_log_text(txt, "max_position = {}".format(self.max_position))
        txt = self.append_log_text(txt, "order_step_size = {}".format(self.order_step_size))
        txt = self.append_log_text(txt, "order_start_size = {}".format(self.order_start_size))
        txt = self.append_log_text(txt, "order_pairs = {}".format(self.order_pairs))
        #txt = self.append_log_text(txt, "curr_balance_value = {}".format(self.curr_balance_value))
        txt = self.append_log_text(txt, "curr_volatility_band_id = {}".format(self.curr_volatility_band_id))
        log_info(self.logger, txt, True)
