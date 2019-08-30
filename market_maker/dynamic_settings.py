import logging
from market_maker.utils.bitmex.utils import XBt_to_XBT
import datetime
from datetime import timedelta
from market_maker.utils.bitmex.log import log_info
from market_maker.settings import settings

DEFAULT_POSITION_MARGIN_TO_WALLET_RATIO_PCT = 0.0386
DEFAULT_ORDER_MARGIN_TO_WALLET_RATIO_PCT = 0.0386
DEFAULT_LEVERAGE = 100
DEFAULT_INITIAL_MARGIN_BASE_PCT = 0.01
DEFAULT_TAKER_FEE_PCT = 0.00075
DEFAULT_MIN_SPREAD_ADJUSTMENT_FACTOR = 0.6
DEFAULT_RELIST_INTERVAL_ADJUSTMENT_FACTOR = 1.2
DEFAULT_MIN_POSITION_SHORTS_ADJUSTMENT_FACTOR = 1.4

PARAMS_UPDATE_INTERVAL = 300  # 5 minutes


# Risk management configuration matrix - pre-configured parameters based on distance to average price (bands) and deposit load values (bands)
RISK_MANAGEMENT_MATRIX = [
    {
        "id": 1,
        "distance_to_avg_price_band_start": 0,
        "distance_to_avg_price_band_end": 1.99999999,
        "deposit_load_band_start": 0,
        "deposit_load_band_end": 24.99999999,
        "risk_profile": "RP1"
    },
    {
        "id": 2,
        "distance_to_avg_price_band_start": 0,
        "distance_to_avg_price_band_end": 1.99999999,
        "deposit_load_band_start": 25,
        "deposit_load_band_end": 49.99999999,
        "risk_profile": "RP2"
    },
    {
        "id": 3,
        "distance_to_avg_price_band_start": 0,
        "distance_to_avg_price_band_end": 1.99999999,
        "deposit_load_band_start": 50,
        "deposit_load_band_end": 74.99999999,
        "risk_profile": "RP3"
    },
    {
        "id": 4,
        "distance_to_avg_price_band_start": 0,
        "distance_to_avg_price_band_end": 1.99999999,
        "deposit_load_band_start": 75,
        "deposit_load_band_end": 999,
        "risk_profile": "RP4"
    },
    {
        "id": 5,
        "distance_to_avg_price_band_start": 2,
        "distance_to_avg_price_band_end": 4.99999999,
        "deposit_load_band_start": 0,
        "deposit_load_band_end": 24.99999999,
        "risk_profile": "RP2"
    },
    {
        "id": 6,
        "distance_to_avg_price_band_start": 2,
        "distance_to_avg_price_band_end": 4.99999999,
        "deposit_load_band_start": 25,
        "deposit_load_band_end": 49.99999999,
        "risk_profile": "RP3"
    },
    {
        "id": 7,
        "distance_to_avg_price_band_start": 2,
        "distance_to_avg_price_band_end": 4.99999999,
        "deposit_load_band_start": 50,
        "deposit_load_band_end": 74.99999999,
        "risk_profile": "RP4"
    },
    {
        "id": 8,
        "distance_to_avg_price_band_start": 2,
        "distance_to_avg_price_band_end": 4.99999999,
        "deposit_load_band_start": 75,
        "deposit_load_band_end": 999,
        "risk_profile": "RP5"
    },
    {
        "id": 9,
        "distance_to_avg_price_band_start": 5,
        "distance_to_avg_price_band_end": 9.99999999,
        "deposit_load_band_start": 0,
        "deposit_load_band_end": 24.99999999,
        "risk_profile": "RP3"
    },
    {
        "id": 10,
        "distance_to_avg_price_band_start": 5,
        "distance_to_avg_price_band_end": 9.99999999,
        "deposit_load_band_start": 25,
        "deposit_load_band_end": 49.99999999,
        "risk_profile": "RP4"
    },
    {
        "id": 11,
        "distance_to_avg_price_band_start": 5,
        "distance_to_avg_price_band_end": 9.99999999,
        "deposit_load_band_start": 50,
        "deposit_load_band_end": 74.99999999,
        "risk_profile": "RP5"
    },
    {
        "id": 12,
        "distance_to_avg_price_band_start": 5,
        "distance_to_avg_price_band_end": 9.99999999,
        "deposit_load_band_start": 75,
        "deposit_load_band_end": 999,
        "risk_profile": "RP6"
    },
    {
        "id": 13,
        "distance_to_avg_price_band_start": 10,
        "distance_to_avg_price_band_end": 999,
        "deposit_load_band_start": 0,
        "deposit_load_band_end": 24.99999999,
        "risk_profile": "RP4"
    },
    {
        "id": 14,
        "distance_to_avg_price_band_start": 10,
        "distance_to_avg_price_band_end": 999,
        "deposit_load_band_start": 25,
        "deposit_load_band_end": 49.99999999,
        "risk_profile": "RP5"
    },
    {
        "id": 15,
        "distance_to_avg_price_band_start": 10,
        "distance_to_avg_price_band_end": 999,
        "deposit_load_band_start": 50,
        "deposit_load_band_end": 74.99999999,
        "risk_profile": "RP6"
    },
    {
        "id": 16,
        "distance_to_avg_price_band_start": 10,
        "distance_to_avg_price_band_end": 999,
        "deposit_load_band_start": 75,
        "deposit_load_band_end": 999,
        "risk_profile": "RP7"
    },
]

RISK_PROFILE_CONFIGURATION = [
    {
        "id": "RP1",
        "risk_level": 70,
        "max_drawdown_pct": 0.15,
        "working_range_pct": 0.04,
        "max_number_dca_orders": 30
    },
    {
        "id": "RP2",
        "risk_level": 60,
        "max_drawdown_pct": 0.285,
        "working_range_pct": 0.06,
        "max_number_dca_orders": 38
    },
    {
        "id": "RP3",
        "risk_level": 50,
        "max_drawdown_pct": 0.48,
        "working_range_pct": 0.08,
        "max_number_dca_orders": 48
    },
    {
        "id": "RP4",
        "risk_level": 40,
        "max_drawdown_pct": 0.90,
        "working_range_pct": 0.12,
        "max_number_dca_orders": 60
    },
    {
        "id": "RP5",
        "risk_level": 30,
        "max_drawdown_pct": 1.5,
        "working_range_pct": 0.16,
        "max_number_dca_orders": 75
    },
    {
        "id": "RP6",
        "risk_level": 20,
        "max_drawdown_pct": 2.25,
        "working_range_pct": 0.20,
        "max_number_dca_orders": 90
    },
    {
        "id": "RP7",
        "risk_level": 10,
        "max_drawdown_pct": 5.00,
        "working_range_pct": 0.40,
        "max_number_dca_orders": 100
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
        self.distance_to_avg_price_pct = 0
        self.deposit_load_pct = 0
        self.deposit_load_intensity = 0

        self.params_last_update = datetime.datetime.now() - timedelta(days=1000)
        self.curr_risk_profile_id = ""
        self.curr_risk_level = 1000000

    def initialize_params(self):
        ticker = self.exchange.get_ticker()
        ticker_last_price = ticker["last"]
        margin = self.exchange.get_margin()
        wallet_balance_XBT = XBt_to_XBT(margin["walletBalance"])
        position = self.exchange.get_position()
        current_qty = position['currentQty']
        avg_entry_price = position['avgEntryPrice']
        distance_to_avg_price_pct = self.get_distance_to_avg_price_pct(current_qty, avg_entry_price, ticker_last_price)
        running_qty = self.exchange.get_delta()
        deposit_load_pct = self.get_deposit_load_pct(running_qty)
        risk_profile = self.get_risk_profile(distance_to_avg_price_pct, deposit_load_pct)

        self.update_dynamic_params(wallet_balance_XBT, ticker_last_price, risk_profile)
        self.update_settings_value("MIN_POSITION", self.min_position)
        self.update_settings_value("MAX_POSITION", self.max_position)

        self.curr_risk_profile_id = ""
        self.curr_risk_level = 1000000

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

    def get_distance_to_avg_price_pct(self, current_qty, avg_entry_price, last_price):
        result = 0
        if current_qty != 0:
            result = abs((last_price - avg_entry_price) * 100 / last_price)
        return result

    def get_deposit_load_pct(self, running_qty):
        if running_qty < 0:
            return abs(running_qty / settings.MIN_POSITION) * 100
        else:
            return abs(running_qty / settings.MAX_POSITION) * 100

    def update_parameters(self):
        result = False
        ticker = self.exchange.get_ticker()
        ticker_last_price = ticker["last"]
        margin = self.exchange.get_margin()
        wallet_balance_XBT = XBt_to_XBT(margin["walletBalance"])
        running_qty = self.exchange.get_delta()
        position = self.exchange.get_position()
        current_qty = position['currentQty']
        avg_entry_price = position['avgEntryPrice']
        self.distance_to_avg_price_pct = self.get_distance_to_avg_price_pct(current_qty, avg_entry_price, ticker_last_price)
        self.deposit_load_pct = self.get_deposit_load_pct(running_qty)
        curr_time = datetime.datetime.now()

        params_seconds_from_last_update = (curr_time - self.params_last_update).total_seconds()
        risk_profile = self.get_risk_profile(self.distance_to_avg_price_pct, self.deposit_load_pct)
        risk_profile_id = risk_profile["id"]
        risk_level = risk_profile["risk_level"]

        is_params_exceeded_update_interval_flag = params_seconds_from_last_update >= PARAMS_UPDATE_INTERVAL
        is_risk_profile_changed_flag = True if risk_profile_id != self.curr_risk_profile_id and (current_qty == 0 or current_qty != 0 and risk_level < self.curr_risk_level) else False

        if is_params_exceeded_update_interval_flag is True and is_risk_profile_changed_flag is True:
            self.update_dynamic_params(wallet_balance_XBT, ticker_last_price, risk_profile)
            self.params_last_update = curr_time
            log_info(self.logger, "Dynamic parameters have been updated!", True)
            result = True

        if result is True:
            self.log_params()

        return result

    def update_dynamic_params(self, last_wallet_balance, ticker_last_price, risk_profile):
        self.curr_risk_profile_id = risk_profile["id"]
        self.curr_risk_level = risk_profile["risk_level"]
        self.max_drawdown_pct = risk_profile["max_drawdown_pct"]
        self.working_range_pct = risk_profile["working_range_pct"]
        self.max_number_dca_orders = risk_profile["max_number_dca_orders"]
        self.interval_pct = round(self.max_drawdown_pct / self.max_number_dca_orders, 8)
        self.min_spread_pct = round(self.interval_pct * 2 * DEFAULT_MIN_SPREAD_ADJUSTMENT_FACTOR, 8)
        self.relist_interval_pct = round(self.interval_pct * DEFAULT_RELIST_INTERVAL_ADJUSTMENT_FACTOR, 8)
        self.order_pairs = int(round(self.working_range_pct / self.interval_pct))

        self.position_margin_amount = round(last_wallet_balance * self.position_margin_pct, 8)
        self.order_margin_amount = round(last_wallet_balance * self.order_margin_pct, 8)
        self.max_possible_position_margin = round(self.position_margin_amount * self.default_leverage * ticker_last_price)
        self.min_position = round(-1 * self.max_possible_position_margin * DEFAULT_MIN_POSITION_SHORTS_ADJUSTMENT_FACTOR)
        self.max_position = round(self.max_possible_position_margin)
        self.order_step_size = self.get_order_step_size(last_wallet_balance)
        self.order_start_size = round(self.max_possible_position_margin / self.max_number_dca_orders - self.order_step_size * (self.max_number_dca_orders - 1) / 2)
        self.deposit_load_intensity = round(self.order_start_size / (100 * self.interval_pct), 8)

    def get_risk_profile(self, distance_to_avg_price_pct, deposit_load_pct):
        for rmm_entry in RISK_MANAGEMENT_MATRIX:
            distance_to_avg_price_band_start = rmm_entry["distance_to_avg_price_band_start"]
            distance_to_avg_price_band_end = rmm_entry["distance_to_avg_price_band_end"]
            deposit_load_band_start = rmm_entry["deposit_load_band_start"]
            deposit_load_band_end = rmm_entry["deposit_load_band_end"]
            risk_profile_id = rmm_entry["risk_profile"]

            if distance_to_avg_price_pct >= distance_to_avg_price_band_start and distance_to_avg_price_pct <= distance_to_avg_price_band_end and deposit_load_pct >= deposit_load_band_start and deposit_load_pct <= deposit_load_band_end:
                for rpc_entry in RISK_PROFILE_CONFIGURATION:
                    id = rpc_entry["id"]
                    if id == risk_profile_id:
                        return rpc_entry

        raise Exception("Unable to retrieve risk profile configuration for the following parameters: distance_to_avg_price_pct={}, deposit_load_pct={}".format(distance_to_avg_price_pct, deposit_load_pct))

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
        txt = self.append_log_text(txt, "distance_to_avg_price_pct = {}%".format(round(self.distance_to_avg_price_pct, 2)))
        txt = self.append_log_text(txt, "deposit_load_pct = {}%".format(round(self.deposit_load_pct, 2)))
        txt = self.append_log_text(txt, "deposit_load_intensity (USD/1% interval) = {}".format(self.deposit_load_intensity))
        txt = self.append_log_text(txt, "curr_risk_profile_id = {}".format(self.curr_risk_profile_id))
        txt = self.append_log_text(txt, "curr_risk_level (1-100) = {}".format(self.curr_risk_level))
        log_info(self.logger, txt, True)
