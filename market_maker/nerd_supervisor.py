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
from market_maker.utils import log, math
from market_maker.db.db_manager import DatabaseManager
from market_maker.backtrader.btrunner import BacktraderRunner
from market_maker.db.model import *
from market_maker.db.quoting_side import *

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

    def get_market_regime(self):
        try:
            market_snapshot = self.btrunner.get_market_snapshot()
            if market_snapshot:
                market_regime = market_snapshot["Indicators"]["Market Regime"]["1h.marketregime"]
                if market_regime > 0:
                    return MarketRegime.BULLISH
                elif market_regime < 0:
                    return MarketRegime.BEARISH
                else:
                    return MarketRegime.NEUTRAL
            else:
                return None
        except Exception as e:
            log_error(logger, "Exception has occurred in MarketInterface.get_market_regime(): {}".format(e), True)
            return None


class NerdSupervisor:
    def __init__(self, mi):
        self.robot_ids_list = DatabaseManager.get_enabled_robots_id_list(settings.EXCHANGE)
        self.mi = mi
        self.curr_market_regime = None
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

    def print_status(self, send_to_telegram):
        """Print the current status of NerdSupervisor"""
        portfolio_positions = DatabaseManager.get_portfolio_positions(logger, self.robot_ids_list)
        portfolio_balance = DatabaseManager.get_portfolio_balance(logger, self.robot_ids_list)

        if self.is_need_to_send_tg_state(portfolio_balance):
            combined_msg = bold("Portfolio Status:\n")
            for position in portfolio_positions:
                if position.exchange and position.current_qty != 0:
                    robot_settings = DatabaseManager.retrieve_robot_settings(position.exchange, position.robot_id)
                    combined_msg += "{}: {}|{}|{}|{}|{:.2f}%|{}\n".format(
                        bold(RobotInfo.parse_for_tg_logs(position.robot_id)),
                        bold(self.get_position_arrow_status(position)),
                        position.symbol,
                        math.get_round_value(position.avg_entry_price, position.tick_log),
                        math.get_round_value(position.current_qty, position.tick_log),
                        position.distance_to_avg_price_pct,
                        robot_settings.quoting_side[0]
                    )
                else:
                    robot_settings = DatabaseManager.retrieve_robot_settings(settings.EXCHANGE, position.robot_id)
                    combined_msg += "{}: {}|{}\n".format(
                        bold(RobotInfo.parse_for_tg_logs(position.robot_id)),
                        "CLOSED",
                        robot_settings.quoting_side[0]
                    )
            combined_msg += "\nLongs/Shorts:"
            for position in portfolio_positions:
                combined_msg += "  {}".format(bold(self.get_position_arrow_status(position)))

            combined_msg += "\nMarket Regime: {}".format(MarketRegime.get_name(self.curr_market_regime))

            num_robots = len(self.robot_ids_list)
            combined_msg += "\nTotal Balance [{} {}]: {}\n".format(num_robots, "robots" if num_robots > 1 else "robot", math.get_round_value(portfolio_balance, 8))
            log_info(logger, combined_msg, send_to_telegram)
            self.last_tg_sent_state = portfolio_balance

    def exit(self, status=settings.FORCE_STOP_EXIT_STATUS_CODE, stackframe=None):
        logger.info("exit(): status={}, stackframe={}".format(status, stackframe))
        logger.info("Shutting down NerdSupervisor ...")

        if not db.is_closed():
            db.close()

        os._exit(status)

    def resolve_quoting_side(self, market_regime):
        if market_regime == MarketRegime.BULLISH:
            return QuotingSide.LONG
        if market_regime == MarketRegime.BEARISH:
            return QuotingSide.SHORT
        if market_regime == MarketRegime.NEUTRAL:
            return QuotingSide.BOTH

    def handle_market_regime_changed(self, market_regime):
        logger.debug("self.curr_market_regime={}, market_regime={}".format(self.curr_market_regime, market_regime))
        if market_regime is not None:
            if market_regime != self.curr_market_regime:
                logger.debug("handle_market_regime_changed(): Market Regime has changed: self.curr_market_regime={}, market_regime={}".format(self.curr_market_regime, market_regime))
                self.curr_market_regime = market_regime
                portfolio_positions = DatabaseManager.get_portfolio_positions(logger, self.robot_ids_list)
                for position in portfolio_positions:
                    if position.current_qty == 0:
                        new_quoting_side = self.resolve_quoting_side(market_regime)
                        DatabaseManager.update_robot_quoting_side(logger, settings.exchange, position.robot_id, new_quoting_side)

    def run_loop(self):
        while True:
            self.print_status(True)
            sleep(DEFAULT_LOOP_INTERVAL)
            market_regime = self.mi.get_market_regime()
            self.handle_market_regime_changed(market_regime)

    def restart(self):
        logger.info("Restarting the NerdSupervisor ...")
        raise ForceRestartException("NerdSupervisor will be restarted")


def run():
    try:
        log_info(logger, '========== Started NerdSupervisor ==========', True)
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