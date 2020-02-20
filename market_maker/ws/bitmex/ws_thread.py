import sys
import websocket
import threading
import traceback
import ssl
from time import sleep
import json
import decimal
import logging
from market_maker.utils.bitmex.utils import XBt_to_XBT
from market_maker.utils.log import log_error, log_info
from market_maker.settings import settings
from market_maker.auth.bitmex.APIKeyAuth import generate_expires, generate_signature
from market_maker.utils.log import setup_bot_custom_logger
from market_maker.utils.math import toNearest
from future.utils import iteritems
from future.standard_library import hooks
with hooks():  # Python 2/3 compat
    from urllib.parse import urlparse, urlunparse
from market_maker.exchange import ExchangeInfo
from market_maker.utils import math
from market_maker.db.db_manager import DatabaseManager

ORDER_POSITION_STATUS_INCREASE = 0
ORDER_POSITION_STATUS_PARTIAL_CLOSE = 1
ORDER_POSITION_STATUS_FULL_CLOSE = 2


# Connects to BitMEX websocket for streaming realtime data.
# The Marketmaker still interacts with this as if it were a REST Endpoint, but now it can get
# much more realtime data without heavily polling the API.
#
# The Websocket offers a bunch of data as raw properties right on the object.
# On connect, it synchronously asks for a push of all this data then returns.
# Right after, the MM can start using its data. It will be updated in realtime, so the MM can
# poll as often as it wants.
class BitMEXWebsocket():

    # Don't grow a table larger than this amount. Helps cap memory usage.
    MAX_TABLE_LEN = 200

    def __init__(self):
        self.logger = logging.getLogger('root')
        self.__reset()

    def __del__(self):
        self.exit()

    def connect(self, endpoint="", symbol="XBTN15", shouldAuth=True):
        '''Connect to the websocket and initialize data stores.'''

        self.logger.debug("Connecting WebSocket.")
        self.symbol = symbol
        self.shouldAuth = shouldAuth

        # We can subscribe right in the connection querystring, so let's build that.
        # Subscribe to all pertinent endpoints
        subscriptions = [sub + ':' + symbol for sub in ["quote", "trade", "instrument"]]
        subscriptions += ["instrument:.BVOL24H"]
        if self.shouldAuth:
            subscriptions += [sub + ':' + symbol for sub in ["order", "execution"]]
            subscriptions += ["margin", "position"]

        # Get WS URL and connect.
        urlParts = list(urlparse(endpoint))
        urlParts[0] = urlParts[0].replace('http', 'ws')
        urlParts[2] = "/realtime?subscribe=" + ",".join(subscriptions)
        wsURL = urlunparse(urlParts)
        self.logger.info("Connecting to %s" % wsURL)
        self.__connect(wsURL)
        self.logger.info('Connected to WS. Waiting for data images, this may take a moment...')

        # Connected. Wait for partials
        self.__wait_for_symbol(symbol)
        if self.shouldAuth:
            self.__wait_for_account()
        self.logger.info('Got all market data. Starting.')

    #
    # Data methods
    #
    def get_instrument(self, symbol):
        instruments = self.data['instrument']
        matchingInstruments = [i for i in instruments if i['symbol'] == symbol]
        if len(matchingInstruments) == 0:
            raise Exception("Unable to find instrument or index with symbol: " + symbol)
        instrument = matchingInstruments[0]
        # Turn the 'tickSize' into 'tickLog' for use in rounding
        # http://stackoverflow.com/a/6190291/832202
        instrument['tickLog'] = math.get_decimal_digits_number(instrument['tickSize'])
        return instrument

    def get_ticker(self, symbol):
        '''Return a ticker object. Generated from instrument.'''

        instrument = self.get_instrument(symbol)

        # If this is an index, we have to get the data from the last trade.
        if instrument['symbol'][0] == '.':
            ticker = {}
            ticker['mid'] = ticker['buy'] = ticker['sell'] = ticker['last'] = instrument['markPrice']
        # Normal instrument
        else:
            bid = instrument['bidPrice'] or instrument['lastPrice']
            ask = instrument['askPrice'] or instrument['lastPrice']
            ticker = {
                "last": instrument['lastPrice'],
                "buy": bid,
                "sell": ask,
                "mid": (bid + ask) / 2
            }

        # The instrument has a tickSize. Use it to round values.
        return {k: toNearest(float(v or 0), instrument['tickSize']) for k, v in iteritems(ticker)}

    def funds(self):
        margin_dict = self.data['margin'][0]
        margin_dict_copy = margin_dict.copy()
        margin_dict_copy["walletBalance"] = XBt_to_XBT(margin_dict["walletBalance"])
        margin_dict_copy["marginBalance"] = XBt_to_XBT(margin_dict["marginBalance"])
        return margin_dict_copy

    def current_qty(self):
        return self.position(self.symbol)['currentQty']

    def open_orders(self, clOrdIDPrefix):
        orders = self.data['order']
        # Filter to only open orders (leavesQty > 0) and those that we actually placed
        return [o for o in orders if str(o['clOrdID']).startswith(clOrdIDPrefix) and o['leavesQty'] > 0]

    def position(self, symbol):
        positions = self.data['position']
        pos = [p for p in positions if p['symbol'] == symbol]
        if len(pos) == 0:
            # No position found; stub it
            return {'avgCostPrice': 0, 'avgEntryPrice': 0, 'currentQty': 0, 'symbol': symbol, 'unrealisedPnl': 0}

        pos_dict = pos[0]
        pos_dict_copy = pos_dict.copy()
        pos_dict_copy["unrealisedPnl"] = XBt_to_XBT(pos_dict["unrealisedPnl"])
        if not pos_dict_copy["avgEntryPrice"]:
            pos_dict_copy["avgEntryPrice"] = 0
        return pos_dict_copy

    #
    # Lifecycle methods
    #
    def error(self, err):
        self._error = err
        log_error(self.logger, err, True)
        self.exit()

    def exit(self):
        self.exited = True
        self.ws.close()

    #
    # Private methods
    #

    def __connect(self, wsURL):
        '''Connect to the websocket in a thread.'''
        self.logger.debug("Starting thread")

        ssl_defaults = ssl.get_default_verify_paths()
        sslopt_ca_certs = {'ca_certs': ssl_defaults.cafile}
        self.ws = websocket.WebSocketApp(wsURL,
                                         on_message=self.__on_message,
                                         on_close=self.__on_close,
                                         on_open=self.__on_open,
                                         on_error=self.__on_error,
                                         header=self.__get_auth()
                                         )

        setup_bot_custom_logger('websocket', log_level=settings.LOG_LEVEL)
        self.wst = threading.Thread(target=lambda: self.ws.run_forever(sslopt=sslopt_ca_certs))
        self.wst.daemon = True
        self.wst.start()
        self.logger.info("Started thread")

        # Wait for connect before continuing
        conn_timeout = settings.TIMEOUT
        while (not self.ws.sock or not self.ws.sock.connected) and conn_timeout and not self._error:
            sleep(1)
            conn_timeout -= 1

        if not conn_timeout or self._error:
            log_error(self.logger, "Couldn't connect to WS! Exiting.", True)
            self.exit()
            sys.exit(settings.FORCE_RESTART_EXIT_STATUS_CODE)

    def __get_auth(self):
        '''Return auth headers. Will use API Keys if present in settings.'''

        if self.shouldAuth is False:
            return []

        self.logger.info("Authenticating with API Key.")
        # To auth to the WS using an API key, we generate a signature of a nonce and
        # the WS API endpoint.
        nonce = generate_expires()
        return [
            "api-expires: " + str(nonce),
            "api-signature: " + generate_signature(ExchangeInfo.get_apisecret(), 'GET', '/realtime', nonce, ''),
            "api-key:" + ExchangeInfo.get_apikey()
        ]

    def __wait_for_account(self):
        '''On subscribe, this data will come down. Wait for it.'''
        # Wait for the keys to show up from the ws
        while not {'margin', 'position', 'order'} <= set(self.data):
            sleep(0.1)

    def __wait_for_symbol(self, symbol):
        '''On subscribe, this data will come down. Wait for it.'''
        while not {'instrument', 'trade', 'quote'} <= set(self.data):
            sleep(0.1)

    def get_order_position_status(self, position_qty, order_side, order_price, order_size):
        self.logger.info("get_order_position_status(): position_qty={}, order_side={}, order_price={}, order_size={}".format(position_qty, order_side, order_price, order_size))
        is_order_long = True if order_side == "Buy" else False
        if position_qty < 0 and is_order_long and abs(position_qty) == order_size or position_qty > 0 and not is_order_long and abs(position_qty) == order_size:
            return ORDER_POSITION_STATUS_FULL_CLOSE
        if position_qty >= 0 and is_order_long or position_qty <= 0 and not is_order_long:
            return ORDER_POSITION_STATUS_INCREASE
        if position_qty > 0 and not is_order_long or position_qty < 0 and is_order_long:
            return ORDER_POSITION_STATUS_PARTIAL_CLOSE

    def __on_message(self, message):
        '''Handler for parsing WS messages.'''
        message = json.loads(message)
        self.logger.debug(json.dumps(message))

        table = message['table'] if 'table' in message else None
        action = message['action'] if 'action' in message else None
        try:
            if 'subscribe' in message:
                if message['success']:
                    self.logger.debug("Subscribed to %s." % message['subscribe'])
                else:
                    log_error(self.logger, "Unable to subscribe to %s. Error: \"%s\" Please check and restart." %
                               (message['request']['args'][0], message['error']), True)
            elif 'status' in message:
                if message['status'] == 400:
                    log_error(self.logger, message['error'], True)
                if message['status'] == 401:
                    log_error(self.logger, "API Key incorrect, please check and restart.", True)
            elif action:

                if table not in self.data:
                    self.data[table] = []

                if table not in self.keys:
                    self.keys[table] = []

                # There are four possible actions from the WS:
                # 'partial' - full table image
                # 'insert'  - new row
                # 'update'  - update row
                # 'delete'  - delete row
                if action == 'partial':
                    self.logger.debug("%s: partial" % table)
                    self.data[table] += message['data']
                    # Keys are communicated on partials to let you know how to uniquely identify
                    # an item. We use it for updates.
                    self.keys[table] = message['keys']
                elif action == 'insert':
                    self.logger.debug('%s: inserting %s' % (table, message['data']))
                    self.data[table] += message['data']

                    # Limit the max length of the table to avoid excessive memory usage.
                    # Don't trim orders because we'll lose valuable state if we do.
                    if table not in ['order', 'orderBookL2'] and len(self.data[table]) > BitMEXWebsocket.MAX_TABLE_LEN:
                        self.data[table] = self.data[table][(BitMEXWebsocket.MAX_TABLE_LEN // 2):]

                elif action == 'update':
                    self.logger.debug('%s: updating %s' % (table, message['data']))
                    # Locate the item in the collection and update it.
                    for updateData in message['data']:
                        item = findItemByKeys(self.keys[table], self.data[table], updateData)
                        if not item:
                            continue  # No item found to update. Could happen before push

                        # Log executions
                        if table == 'order':
                            is_canceled = 'ordStatus' in updateData and updateData['ordStatus'] == 'Canceled'
                            if 'cumQty' in updateData and not is_canceled:
                                curr_position = self.current_qty()
                                order_size = updateData['cumQty'] - item['cumQty']
                                order_side = item['side']
                                symbol = item['symbol']
                                order_price = item['price']
                                order_position_status = self.get_order_position_status(curr_position, order_side, order_price, order_size)
                                if order_position_status == ORDER_POSITION_STATUS_INCREASE:
                                    log_info(self.logger, "Execution (position increase): {} {} contracts of {} at {}".format(order_side, order_size, symbol, order_price), True)
                                elif order_position_status == ORDER_POSITION_STATUS_PARTIAL_CLOSE:
                                    log_info(self.logger, "Execution (position partial close): {} {} contracts of {} at {}".format(order_side, order_size, symbol, order_price), True)
                                elif order_position_status == ORDER_POSITION_STATUS_FULL_CLOSE:
                                    log_info(self.logger, "Execution (position fully closed): {} {} contracts of {} at {}".format(order_side, order_size, symbol, order_price), True)
                                    DatabaseManager.set_quoting_side_bot_settings(self.logger, settings.EXCHANGE, settings.BOTID, curr_position)

                        # Update this item.
                        item.update(updateData)

                        # Remove canceled / filled orders
                        if table == 'order' and item['leavesQty'] <= 0:
                            self.data[table].remove(item)

                elif action == 'delete':
                    self.logger.debug('%s: deleting %s' % (table, message['data']))
                    # Locate the item in the collection and remove it.
                    for deleteData in message['data']:
                        item = findItemByKeys(self.keys[table], self.data[table], deleteData)
                        self.data[table].remove(item)
                else:
                    raise Exception("Unknown action: %s" % action)
        except:
            log_error(self.logger, traceback.format_exc(), True)

    def __on_open(self):
        self.logger.debug("Websocket Opened.")

    def __on_close(self):
        self.logger.info('Websocket Closed')
        self.exit()

    def __on_error(self, error):
        if not self.exited:
            self.error(error)

    def __reset(self):
        self.data = {}
        self.keys = {}
        self.exited = False
        self._error = None


def findItemByKeys(keys, table, matchData):
    for item in table:
        matched = True
        for key in keys:
            if item[key] != matchData[key]:
                matched = False
        if matched:
            return item

if __name__ == "__main__":
    # create console handler and set level to debug
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # add formatter to ch
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ws = BitMEXWebsocket()
    ws.logger = logger
    ws.connect("https://testnet.bitmex.com/api/v1")
    while(ws.ws.sock.connected):
        sleep(1)

