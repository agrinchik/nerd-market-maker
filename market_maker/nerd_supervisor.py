from __future__ import absolute_import
from time import sleep
import os

import atexit
import signal
import threading
from common.exception import *
from common.robot_info import RobotInfo
from market_maker.utils.log import log_info
from market_maker.utils.log import log_error
from market_maker.settings import settings
from market_maker.utils import log, math
from market_maker.db.model import *
from market_maker.db.db_manager import DatabaseManager
from market_maker.db.quoting_side import *
from market_maker.backtrader.btrunner import BacktraderRunner


DEFAULT_LOOP_INTERVAL = 1

logger = log.setup_supervisor_custom_logger('root')


class NerdSupervisor:
    def __init__(self):
        self.btt = None
        self.last_tg_sent_state = None
        atexit.register(self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        logger.info("NerdSupervisor initializing...")

    def get_portfolio_positions(self):
        try:
            robot_id_list = DatabaseManager.get_robot_id_list(settings.NUMBER_OF_ROBOTS)
            query = Position.select().where(Position.robot_id.in_(robot_id_list))
            return query
        except Exception as e:
            log_error(logger, "Database exception has occurred: {}. Restarting the NerdSupervisor ...".format(e), True)
            self.restart()

    def get_portfolio_balance(self):
        try:
            robot_id_list = DatabaseManager.get_robot_id_list(settings.NUMBER_OF_ROBOTS)
            query = Wallet.select(fn.SUM(Wallet.wallet_balance))\
                          .where(Wallet.robot_id.in_(robot_id_list))
            return query.scalar()
        except Exception as e:
            log_error(logger, "Database exception has occurred: {}. Restarting the NerdSupervisor ...".format(e), True)
            self.restart()

    def is_need_to_send_tg_state(self, data):
        return self.last_tg_sent_state != data

    def get_position_arrow_status(self, position):
        if position.current_qty > 0:
            return "⇧"
        if position.current_qty < 0:
            return "⇩"
        return "-"

    def print_status(self, send_to_telegram):
        """Print the current status of NerdSupervisor"""
        num_robots = settings.NUMBER_OF_ROBOTS
        portfolio_positions = self.get_portfolio_positions()
        portfolio_balance = self.get_portfolio_balance()

        if self.is_need_to_send_tg_state(portfolio_balance):
            combined_msg = "<b>Portfolio Status:</b>\n"
            for position in portfolio_positions:
                robot_settings = DatabaseManager.retrieve_robot_settings(position.exchange, position.robot_id)
                effective_quoting_side = QuotingSide.get_effective_quoting_side(robot_settings)
                if position.exchange and position.current_qty != 0:
                    combined_msg += "<b>{}:</b> <b>{}</b>|{}|{}|{}|{:.2f}%|{}:{}\n".format(
                        RobotInfo.parse_for_tg_logs(position.robot_id),
                        self.get_position_arrow_status(position),
                        position.symbol,
                        math.get_round_value(position.avg_entry_price, position.tick_log),
                        math.get_round_value(position.current_qty, position.tick_log),
                        position.distance_to_avg_price_pct,
                        robot_settings.quoting_mode[0],
                        effective_quoting_side[0]
                    )
                else:
                    combined_msg += "<b>{}:</b> {}|{}:{}\n".format(
                        RobotInfo.parse_for_tg_logs(position.robot_id),
                        "CLOSED",
                        robot_settings.quoting_mode[0],
                        effective_quoting_side[0]
                    )
            combined_msg += "\nLongs/Shorts:"
            for position in portfolio_positions:
                combined_msg += "  <b>{}</b>".format(self.get_position_arrow_status(position))

            combined_msg += "\n\nTotal Balance [{} {}]: {}\n".format(num_robots, "robots" if num_robots > 1 else "robot", math.get_round_value(portfolio_balance, 8))
            log_info(logger, combined_msg, send_to_telegram)
            self.last_tg_sent_state = portfolio_balance

    def exit(self, status=settings.FORCE_STOP_EXIT_STATUS_CODE, stackframe=None):
        logger.info("exit(): status={}, stackframe={}".format(status, stackframe))
        logger.info("Shutting down NerdSupervisor ...")

        if not db.is_closed():
            db.close()

        os._exit(status)

    def bt_thread(self):
        btrunner = BacktraderRunner()
        btrunner.start()

    def start_backtrader_daemon(self):
        self.btt = threading.Thread(name="BT Thread", target=self.bt_thread)
        self.btt.daemon = True
        self.btt.start()
        logger.info("Started Backtrader Daemon")

    def run_loop(self):
        while True:
            self.print_status(True)
            sleep(DEFAULT_LOOP_INTERVAL)

    def restart(self):
        logger.info("Restarting the NerdSupervisor ...")
        raise ForceRestartException("NerdSupervisor will be restarted")


def run():
    log_info(logger, 'Started NerdSupervisor', True)

    ns = NerdSupervisor()
    try:
        ns.start_backtrader_daemon()

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
