from __future__ import absolute_import
from time import sleep
import os

import atexit
import signal
from common.exception import *
from common.bot_info import BotInfo
from market_maker.utils.log import log_info
from market_maker.utils.log import log_error
from market_maker.settings import settings
from market_maker.utils import log, math
from market_maker.db.model import *

DEFAULT_LOOP_INTERVAL = 1

logger = log.setup_supervisor_custom_logger('root')


class NerdSupervisor:
    def __init__(self):
        self.last_tg_sent_state = None
        atexit.register(self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        logger.info("NerdSupervisor initializing...")

        # Connect to database.
        db.connect()

    def get_bot_id_list(self):
        return [BotInfo.parse_from_number(i) for i in range(1, settings.NUMBER_OF_BOTS + 1)]

    def get_portfolio_positions(self):
        try:
            bot_id_list = self.get_bot_id_list()
            query = Position.select()\
                            .where(Position.bot_id.in_(bot_id_list))
            return query
        except Exception as e:
            log_error(logger, "Database exception has occurred: {}. Restarting the NerdSupervisor ...".format(e), True)
            self.restart()

    def get_portfolio_balance(self):
        try:
            bot_id_list = self.get_bot_id_list()
            query = Wallet.select(fn.SUM(Wallet.wallet_balance))\
                          .where(Wallet.bot_id.in_(bot_id_list))
            return query.scalar()
        except Exception as e:
            log_error(logger, "Database exception has occurred: {}. Restarting the NerdSupervisor ...".format(e), True)
            self.restart()

    def is_need_to_send_tg_state(self, data):
        return self.last_tg_sent_state != data

    def print_status(self, send_to_telegram):
        """Print the current status of NerdSupervisor"""
        num_bots = settings.NUMBER_OF_BOTS
        portfolio_positions = self.get_portfolio_positions()
        portfolio_balance = self.get_portfolio_balance()

        if self.is_need_to_send_tg_state(portfolio_balance):
            combined_msg = "<b>PORTFOLIO STATUS:</b>\n"
            for position in portfolio_positions:
                combined_msg += "<b>{}:</b> {}|{}|{}|{}|{}\n".format(
                    position.bot_id,
                    "LONG" if position.is_long else "SHORT",
                    position.symbol,
                    math.get_round_value(position.avg_entry_price, position.tick_log),
                    math.get_round_value(position.current_qty, position.tick_log),
                    math.get_round_value(position.unrealised_pnl, position.tick_log)
                )
            combined_msg += "\nLongs/Shorts:"
            for position in portfolio_positions:
                combined_msg += "  <b>{}</b>".format("⇧" if position.is_long else "⇩")

            combined_msg += "\n\nBalance [{} {}]: {}\n".format(num_bots, "bots" if num_bots > 1 else "bot", math.get_round_value(portfolio_balance, 8))
            log_info(logger, combined_msg, send_to_telegram)
            self.last_tg_sent_state = portfolio_balance

    def exit(self, status=settings.FORCE_STOP_EXIT_STATUS_CODE, stackframe=None):
        logger.info("exit(): status={}, stackframe={}".format(status, stackframe))
        logger.info("Shutting down NerdSupervisor ...")

        if not db.is_closed():
            db.close()

        os._exit(status)

    def run_loop(self):
        while True:
            logger.debug("*" * 100)
            self.print_status(True)
            sleep(DEFAULT_LOOP_INTERVAL)

    def restart(self):
        logger.info("Restarting the NerdSupervisor ...")
        raise ForceRestartException("NerdSupervisor will be restarted")


def run():
    log_info(logger, 'Started NerdSupervisor', True)

    ns = NerdSupervisor()
    try:
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
