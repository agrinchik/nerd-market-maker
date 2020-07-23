from __future__ import absolute_import
from time import sleep
import os
import signal
from market_maker.utils.log import log_debug
from market_maker.utils.log import log_info
from market_maker.utils.log import log_error
from common.exception import *
from market_maker import bitmex
from market_maker import bitfinex
from market_maker.settings import settings
from market_maker.utils.bitmex import errors
from market_maker.utils import log
from market_maker.exchange import ExchangeInfo
from market_maker.db.model import *
from datetime import datetime
from market_maker.db.db_manager import DatabaseManager
from market_maker.strategies.config.strategy_factory import StrategyFactory

logger = log.setup_robot_custom_logger('root')


class ExchangeInterface:
    def __init__(self):
        self.symbol = settings.SYMBOL
        self.xchange = self.create_exchange_interface()

    def create_exchange_interface(self):
        result = None
        if ExchangeInfo.is_bitmex():
            prefix = "{}_{}".format(settings.ROBOTID, settings.ORDERID_PREFIX)
            result = bitmex.BitMEX(symbol=self.symbol,
                                    orderIDPrefix=prefix, postOnly=settings.POST_ONLY,
                                    timeout=settings.TIMEOUT,
                                    retries=settings.RETRIES,
                                    retry_delay=settings.RETRY_DELAY)
        elif ExchangeInfo.is_bitfinex():
            result = bitfinex.Bitfinex(symbol=self.symbol)

        return result

    def cancel_all_orders(self):
        logger.info("Resetting current position. Cancelling all existing orders.")

        # In certain cases, a WS update might not make it through before we call this.
        # For that reason, we grab via HTTP to ensure we grab them all.
        orders = self.xchange.http_open_orders()

        for order in orders:
            logger.info("Cancelling: {} {} @ {}".format(order['side'], order['orderQty'], order['price']))

        if len(orders):
            logger.info("Cancelling all orders: {}".format(orders))
            result = self.xchange.cancel_orders(orders)
            logger.info("Cancelling all orders result={}".format(result))
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
        curr_quantity = position['currentQty']
        avg_entry_price = position['avgEntryPrice']
        if curr_quantity != 0:
            if curr_quantity > 0:
                result = round((last_price - avg_entry_price) * 100 / avg_entry_price, 2)
            else:
                result = round((avg_entry_price - last_price) * 100 / avg_entry_price, 2)
        return result

    def get_unrealized_pnl(self):
        return self.get_position()['unrealisedPnl']

    def get_unrealized_pnl_pct(self):
        result = 0
        unrealized_pnl = self.get_unrealized_pnl()
        margin = self.get_margin()
        wallet_balance = margin["walletBalance"]
        result = 100 * unrealized_pnl / wallet_balance
        return result

    def get_distance_to_liq_price_pct(self):
        result = 0
        position = self.get_position()
        last_price = self.get_ticker()["last"]
        if position['currentQty'] != 0:
            result = abs(round((last_price - position['liquidationPrice']) * 100 / last_price, 2))
        return result

    def get_margin(self):
        return self.xchange.funds()

    def get_orders(self):
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
        return self.xchange.is_open()

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

    def create_bulk_orders(self, orders):
        return self.xchange.create_bulk_orders(orders)

    def amend_bulk_orders(self, orders):
        return self.xchange.amend_bulk_orders(orders)

    def cancel_bulk_orders(self, orders):
        return self.xchange.cancel_orders(orders)


class NerdMarketMakerRobot:
    def __init__(self):
        self.exchange = ExchangeInterface()
        # Once exchange is created, register exit handler that will always cancel orders
        # on any error.
        #atexit.register(self.exit) TODO: Need to review
        signal.signal(signal.SIGTERM, self.exit)

        logger.info("Using symbol %s." % self.exchange.symbol)
        logger.info("NerdMarketMakerRobot initializing, connecting to exchange. Live run: executing real trades.")

        robot_settings = DatabaseManager.retrieve_robot_settings(logger, settings.EXCHANGE, settings.ROBOTID)
        self.strategy = StrategyFactory.build_strategy(robot_settings.strategy, logger, self.exchange)

        self.curr_market_snapshot = None
        self.start_time = datetime.now()
        self.is_trading_suspended = False
        self.price_change_last_check = datetime.now()
        self.price_change_last_price = -1
        self.reset()

    def whereAmI(self):
        return os.path.dirname(os.path.realpath(__import__("__main__").__file__))

    def reset(self):
        self.exchange.cancel_all_orders()
        self.strategy.check_suspend_trading()
        self.strategy.dynamic_settings.initialize_params()

    def check_connection(self):
        """Ensure the WS connections are still open."""
        return self.exchange.is_open()

    def update_db(self):
        position = self.exchange.get_position()
        margin = self.exchange.get_margin()
        instrument = self.exchange.get_instrument(position["symbol"])
        DatabaseManager.update_wallet_db(logger, position, margin)
        DatabaseManager.update_position_db(logger, self.exchange, position, instrument)

    def exit(self, status=settings.FORCE_STOP_EXIT_STATUS_CODE, stackframe=None):
        logger.info("exit(): status={}, stackframe={}".format(status, stackframe))
        logger.info("Shutting down. All open orders will be cancelled.")
        try:
            self.exchange.cancel_all_orders()
            self.exchange.xchange.exit()
            self.update_db()
        except errors.AuthenticationError as ae:
            logger.info("Was not authenticated; could not cancel orders.")
        except ForceRestartException as fre:
            logger.info("Exception occurred: {}".format(fre))
        except Exception as e:
            logger.info("Unable to cancel orders: %s" % e)

        if not db.is_closed():
            db.close()

        os._exit(status)

    def run_loop(self):
        while True:
            logger.debug("*" * 100)

            # This will restart on very short downtime, but if it's longer,
            # the MM will crash entirely as it is unable to connect to the WS on boot.
            if not self.check_connection():
                RESTART_TIMEOUT = 60
                log_error(logger, "Realtime data connection unexpectedly closed, restarting in {} seconds.".format(RESTART_TIMEOUT), True)
                sleep(RESTART_TIMEOUT)
                self.restart()

            self.strategy.on_market_snapshot_update()
            if self.strategy.is_market_snapshot_initialized():
                self.strategy.update_dynamic_app_settings(False)
                self.strategy.sanity_check()       # Ensures health of mm - several cut-out points here
                self.strategy.print_status(False)  # Print skew, delta, etc
                self.strategy.check_suspend_trading()
                self.strategy.place_orders()       # Creates desired orders and converges to existing orders
                self.update_db()

            sleep(settings.LOOP_INTERVAL)

    def restart(self):
        logger.info("Restarting the NerdMarketMakerRobot ...")
        raise ForceRestartException("NerdMarketMakerRobot will be restarted")


def run():
    log_info(logger, 'Started NerdMarketMakerRobot\nRobotID: {}\nExchange: {}\nSymbol: {}'.format(settings.ROBOTID, settings.EXCHANGE, settings.SYMBOL), True)

    nmmr = NerdMarketMakerRobot()
    try:
        nmmr.run_loop()
    except ForceRestartException as fe:
        nmmr.exit(settings.FORCE_RESTART_EXIT_STATUS_CODE)
    except KeyboardInterrupt as ki:
        nmmr.exit(settings.FORCE_STOP_EXIT_STATUS_CODE)
    except SystemExit as se:
        nmmr.exit(se.code)
    except Exception as e:
        log_error(logger, "UNEXPECTED EXCEPTION! {}\nNerdMarketMakerRobot will be restarted.".format(e), True)
        nmmr.exit(settings.FORCE_RESTART_EXIT_STATUS_CODE)


if __name__ == "__main__":
    run()
