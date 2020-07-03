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
                market_regime_hist = market_snapshot["Indicators"]["Market Regime"]["1h.marketregime_hist"]
                return market_regime_hist
            else:
                return None
        except Exception as e:
            log_error(logger, "Exception has occurred in MarketInterface.get_market_regime(): {}".format(e), True)
            return None


class NerdSupervisor:
    def __init__(self, mi):
        self.robot_ids_list = DatabaseManager.get_enabled_robots_id_list(logger, settings.EXCHANGE)
        self.mi = mi
        self.curr_market_regime_hist = None
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
                        math.get_round_value(position.avg_entry_price, position.tick_log),
                        math.get_round_value(position.current_qty, position.tick_log),
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

            combined_msg += "\n{} {}".format(bold("Mkt Regime:"), MarketRegime.get_name(self.curr_market_regime_hist[-1]) if self.curr_market_regime_hist else "N/A")
            if self.curr_market_regime_hist and len(self.curr_market_regime_hist) > 0:
                combined_msg += "\n{} {} {} {} {} {}".format(bold("Mkt Regime Hist:"), round(self.curr_market_regime_hist[0]), round(self.curr_market_regime_hist[1]),
                                                            round(self.curr_market_regime_hist[2]), round(self.curr_market_regime_hist[3]), round(self.curr_market_regime_hist[4]))

            num_robots = len(self.robot_ids_list)
            combined_msg += "\n{} [{} {}]: {}\n".format(bold("Total Balance"), bold(num_robots), bold("robots" if num_robots > 1 else "robot"), math.get_round_value(portfolio_balance, 8))
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
        if market_regime == MarketRegime.RANGE:
            return QuotingSide.BOTH

    def check_market_regime_changed(self, robot_settings_dict, market_regime_hist, portfolio_positions):
        logger.debug("self.market_regime_hist={}".format(market_regime_hist))
        if market_regime_hist is not None and len(market_regime_hist) > 1:
            new_market_regime = market_regime_hist[-1]
            prev_market_regime = self.curr_market_regime_hist[-1] if self.curr_market_regime_hist and len(self.curr_market_regime_hist) > 1 else None
            self.curr_market_regime_hist = market_regime_hist
            if new_market_regime != prev_market_regime:
                log_info(logger, "Market Regime has changed: {} => {}".format(MarketRegime.get_name(prev_market_regime), MarketRegime.get_name(new_market_regime)), True)
            new_quoting_side = self.resolve_quoting_side(new_market_regime)
            for position in portfolio_positions:
                pos_robot_id = position.robot_id
                pos_exchange = position.exchange
                robot_quoting_side = robot_settings_dict[pos_robot_id].quoting_side
                if position.current_qty == 0 and new_quoting_side != robot_quoting_side:
                    DatabaseManager.update_robot_quoting_side(logger, pos_exchange, position.robot_id, new_quoting_side)
                    log_info(logger, "As {} has no open positions and quoting side has changed, setting the new quoting side={}".format(position.robot_id, new_quoting_side), True)

    def run_loop(self):
        while True:
            robot_settings_dict = DatabaseManager.get_enabled_robots_dict(logger, settings.EXCHANGE)
            portfolio_positions = DatabaseManager.get_portfolio_positions(logger, self.robot_ids_list)
            portfolio_balance = DatabaseManager.get_portfolio_balance(logger, self.robot_ids_list)
            self.print_status(portfolio_positions, portfolio_balance, True)
            sleep(DEFAULT_LOOP_INTERVAL)
            market_regime_hist = self.mi.get_market_regime()
            self.check_market_regime_changed(robot_settings_dict, market_regime_hist, portfolio_positions)

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