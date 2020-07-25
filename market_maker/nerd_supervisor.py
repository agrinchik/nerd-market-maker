from __future__ import absolute_import
from time import sleep
import os

import atexit
import signal
import threading
from common.exception import *
from common.robot_info import RobotInfo
from market_maker.db.market_regime import MarketRegime
from market_maker.utils.log import log_info
from market_maker.utils.log import log_error
from market_maker.settings import settings
from market_maker.utils import log, mm_math
from market_maker.db.db_manager import DatabaseManager
from market_maker.backtrader.btrunner import BacktraderRunner
from market_maker.db.model import *
import math

CHAR_ARROW_UP = "⇧"
CHAR_ARROW_DOWN = "⇩"
CHAR_HYPHEN = "-"
DEFAULT_LOOP_INTERVAL = 1
logger = log.setup_supervisor_custom_logger('root')


def bold(txt):
    return "<b>{}</b>".format(txt)


class MarketInterface:
    def __init__(self):
        self.mit = None
        self.btrunner = None

    def mi_thread(self):
        self.btrunner = BacktraderRunner()
        self.btrunner.start()

    def start(self):
        self.mit = threading.Thread(name="Market Interface Thread", target=self.mi_thread)
        self.mit.daemon = True
        self.mit.start()
        logger.info("********* Started Market Interface *********")

    def get_market_snapshot(self, exchange, symbol):
        try:
            return self.btrunner.get_market_snapshot(exchange, symbol)
        except Exception as e:
            log_error(logger, "Exception has occurred in MarketInterface.get_market_snapshot(): {}".format(e), True)
            return None


class NerdSupervisor:
    def __init__(self, mi):
        self.robot_ids_list = DatabaseManager.get_enabled_robots_id_list(logger, settings.EXCHANGE)
        self.mi = mi
        self.curr_market_snapshot = None
        self.last_tg_sent_state = None
        atexit.register(self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        logger.info("NerdSupervisor initializing...")

    def is_need_to_send_tg_state(self, data):
        return self.last_tg_sent_state != data

    def get_position_arrow_status(self, position):
        if position.current_qty > 0:
            return CHAR_ARROW_UP
        if position.current_qty < 0:
            return CHAR_ARROW_DOWN
        return CHAR_HYPHEN

    def get_pct_value(self, val):
        if isinstance(val, str):
            return val
        return "{}%".format(round(val * 100, 2))

    def print_status(self, portfolio_positions, portfolio_balance, send_to_telegram):
        """Print the current status of NerdSupervisor"""

        if self.is_need_to_send_tg_state(portfolio_balance):
            combined_msg = bold("Portfolio Status:\n")
            for position in portfolio_positions:
                if position.exchange and position.current_qty != 0:
                    robot_settings = DatabaseManager.retrieve_robot_settings(logger, position.exchange, position.robot_id)
                    combined_msg += "{}: {}|{}|{}|{}|{:.2f}%|{}\n".format(
                        bold(RobotInfo.parse_for_tg_logs(position.robot_id)),
                        bold(self.get_position_arrow_status(position)),
                        position.symbol,
                        mm_math.get_round_value(position.avg_entry_price, position.tick_log),
                        mm_math.get_round_value(position.current_qty, position.tick_log),
                        position.distance_to_avg_price_pct,
                        robot_settings.quoting_side
                    )
                else:
                    robot_settings = DatabaseManager.retrieve_robot_settings(logger, settings.EXCHANGE, position.robot_id)
                    combined_msg += "{}: {}|{}\n".format(
                        bold(RobotInfo.parse_for_tg_logs(position.robot_id)),
                        "CLOSED",
                        robot_settings.quoting_side
                    )
            combined_msg += bold("\nLongs/Shorts:")
            for position in portfolio_positions:
                combined_msg += "  {}".format(bold(self.get_position_arrow_status(position)))

            combined_msg += "\n{} {} | {}".format(bold("ATR (1m | 5m):"), self.get_pct_value(self.curr_market_snapshot.atr_pct_1m) if self.curr_market_snapshot else "N/A", self.get_pct_value(self.curr_market_snapshot.atr_pct_5m) if self.curr_market_snapshot else "N/A")
            combined_msg += "\n{} {}".format(bold("Mkt Regime (1m):"), MarketRegime.get_name(self.curr_market_snapshot.marketregime_1m) if self.curr_market_snapshot else "N/A")

            num_robots = len(self.robot_ids_list)
            combined_msg += "\n{} [{} {}]: {}\n".format(bold("Total Balance"), bold(num_robots), bold("robots" if num_robots > 1 else "robot"), mm_math.get_round_value(portfolio_balance, 8))
            log_info(logger, combined_msg, send_to_telegram)
            self.last_tg_sent_state = portfolio_balance

    def exit(self, status=settings.FORCE_STOP_EXIT_STATUS_CODE, stackframe=None):
        logger.info("exit(): status={}, stackframe={}".format(status, stackframe))
        logger.info("Shutting down NerdSupervisor ...")

        if not db.is_closed():
            db.close()

        os._exit(status)

    def on_market_snapshot_update(self, market_snapshot):
        if market_snapshot:
            logger.debug("self.market_snapshot={}".format(market_snapshot))
            prev_market_regime = self.curr_market_snapshot.marketregime_1m if self.curr_market_snapshot else None
            prev_atr = self.curr_market_snapshot.atr_pct_1m if self.curr_market_snapshot else "N/A"
            new_market_regime = market_snapshot.marketregime_1m
            new_atr = market_snapshot.atr_pct_1m
            is_atr_changed = prev_atr != new_atr and not math.isnan(new_atr)
            is_market_regime_changed = prev_market_regime != new_market_regime and not math.isnan(new_market_regime)
            if is_atr_changed or is_market_regime_changed:
                log_info(logger, "Market Snapshot has been updated:\nATR (1 min): {} => {}\nMarket Regime: {} => {}".format(self.get_pct_value(prev_atr), self.get_pct_value(new_atr), MarketRegime.get_name(prev_market_regime), MarketRegime.get_name(new_market_regime)), True)
                DatabaseManager.update_market_snapshot(logger, market_snapshot)
                self.curr_market_snapshot = market_snapshot

    def get_symbol(self, robot_settings_dict):
        robot_settings = robot_settings_dict[self.robot_ids_list[0]]
        return robot_settings.symbol

    def run_loop(self):
        while True:
            robot_settings_dict = DatabaseManager.get_enabled_robots_dict(logger, settings.EXCHANGE)
            portfolio_positions = DatabaseManager.get_portfolio_positions(logger, self.robot_ids_list)
            portfolio_balance = DatabaseManager.get_portfolio_balance(logger, self.robot_ids_list)
            symbol = self.get_symbol(robot_settings_dict)
            market_snapshot = self.mi.get_market_snapshot(settings.EXCHANGE, symbol)
            self.on_market_snapshot_update(market_snapshot)
            self.print_status(portfolio_positions, portfolio_balance, True)
            sleep(DEFAULT_LOOP_INTERVAL)

    def restart(self):
        logger.info("Restarting the NerdSupervisor ...")
        raise ForceRestartException("NerdSupervisor will be restarted")


def run():
    try:
        log_info(logger, "========== Started NerdSupervisor ==========", True)
        mi = MarketInterface()
        mi.start()

        ns = NerdSupervisor(mi)
        ns.run_loop()

    except ForceRestartException as fe:
        ns.exit(settings.FORCE_RESTART_EXIT_STATUS_CODE)
    except KeyboardInterrupt as ki:
        ns.exit(settings.FORCE_STOP_EXIT_STATUS_CODE)
    except SystemExit as se:
        ns.exit(se.code)
    except Exception as e:
        log_error(logger, "UNEXPECTED EXCEPTION! {}\nNerdSupervisor will be terminated.".format(e), True)
        ns.exit(settings.FORCE_STOP_EXIT_STATUS_CODE)


if __name__ == "__main__":
    run()