#!/usr/bin/python
"""Bitfinex Rest API V2 implementation"""
# pylint: disable=R0904

from __future__ import absolute_import
import json
from json.decoder import JSONDecodeError
import hmac
import hashlib
import requests
from market_maker.utils.bitfinex import utils

PROTOCOL = "https"
HOST = "api.bitfinex.com"
VERSION = "v2"


# HTTP request timeout in seconds
TIMEOUT = 5.0


class BitfinexException(Exception):
    """
    Exception handler
    """
    pass


class Client:
    """Client for the bitfinex.com API REST V2.
    Link for official bitfinex documentation :

    `Bitfinex rest2 docs <https://bitfinex.readme.io/v2/docs>`_

    `Bitfinex rest2 reference <https://bitfinex.readme.io/v2/reference>`_

    Parameters
    ----------
    key : str
        Bitfinex api key

    secret : str
        Bitfinex api secret

    nonce_multiplier : Optional float
        Multiply nonce by this number

    Examples
    --------
     ::

        bfx_client = Client(key,secret)

        bfx_client = Client(key,secret,2.0)
    """

    def __init__(self, key=None, secret=None, nonce_multiplier=1.0):
        """
        Object initialisation takes 2 mandatory arguments key and secret and a optional one
        nonce_multiplier
        """

        assert isinstance(nonce_multiplier, float), "nonce_multiplier must be decimal"
        self.base_url = "%s://%s/" % (PROTOCOL, HOST)
        self.key = key
        self.secret = secret
        self.nonce_multiplier = nonce_multiplier

    def _nonce(self):
        """Returns a nonce used in authentication.
        Nonce must be an increasing number, if the API key has been used
        earlier or other frameworks that have used higher numbers you might
        need to increase the nonce_multiplier."""
        return str(utils.get_nonce(self.nonce_multiplier))

    def _headers(self, path, nonce, body):
        """
        create signed headers
        """
        signature = "/api/{}{}{}".format(path, nonce, body)
        hmc = hmac.new(self.secret.encode('utf8'), signature.encode('utf8'), hashlib.sha384)
        signature = hmc.hexdigest()

        return {
            "bfx-nonce": nonce,
            "bfx-apikey": self.key,
            "bfx-signature": signature,
            "content-type": "application/json"
        }

    def _post(self, path, payload, verify=False):
        """
        Send post request to bitfinex
        """
        nonce = self._nonce()
        headers = self._headers(path, nonce, payload)
        response = requests.post(self.base_url + path, headers=headers, data=payload, verify=verify)

        if response.status_code == 200:
            return response.json()
        else:
            try:
                content = response.json()
            except JSONDecodeError:
                content = response.text()
            raise BitfinexException(response.status_code, response.reason, content)

    def _get(self, path, **params):
        """
        Send get request to bitfinex
        """
        url = self.base_url + path
        response = requests.get(url, timeout=TIMEOUT, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            try:
                content = response.json()
            except JSONDecodeError:
                content = response.text()
            raise BitfinexException(response.status_code, response.reason, content)

    # REST PUBLIC ENDPOINTS
    def platform_status(self):
        """
        .. _platform_status:

        `Bitfinex platform_status reference
        <https://bitfinex.readme.io/v2/reference#rest-public-platform-status>`_

        Get the current status of the platform. Maintenance periods last for just few minutes and
        might be necessary from time to time during upgrades of core components of our
        infrastructure. Even if rare it is important to have a way to notify users. For a real-time
        notification we suggest to use websockets and listen to events 20060/20061

        Returns
        -------
        int
            - 1 = operative
            - 0 = maintenance

        Example
        -------
         ::

            bfx_client.platform_status()

        """
        path = "v2/platform/status"
        response = self._get(path)
        return response

    def tickers(self, symbol_list):
        """`Bitfinex tickers reference
        <https://bitfinex.readme.io/v2/reference#rest-public-tickers>`_

        The ticker is a high level overview of the state of the market. It shows you the current
        best bid and ask, as well as the last trade price.It also includes information such as daily
        volume and how much the price has moved over the last day.

        Parameters
        ----------
        symbol_list : list
            The symbols you want information about as a comma separated list,
            or ALL for every symbol.

        Returns
        -------
        list
             ::

                [
                  # on trading pairs (ex. tBTCUSD)
                  [
                    SYMBOL,
                    BID,
                    BID_SIZE,
                    ASK,
                    ASK_SIZE,
                    DAILY_CHANGE,
                    DAILY_CHANGE_PERC,
                    LAST_PRICE,
                    VOLUME,
                    HIGH,
                    LOW
                  ],
                  # on funding currencies (ex. fUSD)
                  [
                    SYMBOL,
                    FRR,
                    BID,
                    BID_SIZE,
                    BID_PERIOD,
                    ASK,
                    ASK_SIZE,
                    ASK_PERIOD,
                    DAILY_CHANGE,
                    DAILY_CHANGE_PERC,
                    LAST_PRICE,
                    VOLUME,
                    HIGH,
                    LOW
                  ],
                  ...
                ]

        Note
        ----
            ================= ===== ================================================================
            Field             Type  Description
            ================= ===== ================================================================
            FRR               float Flash Return Rate - average of all fixed rate funding over the
                                    last hour
            BID               float Price of last highest bid
            BID_PERIOD        int   Bid period covered in days
            BID_SIZE          float Sum of the 25 highest bid sizes
            ASK               float Price of last lowest ask
            ASK_PERIOD        int   Ask period covered in days
            ASK_SIZE          float Sum of the 25 lowest ask sizes
            DAILY_CHANGE      float Amount that the last price has changed since yesterday
            DAILY_CHANGE_PERC float Amount that the price has changed expressed in percentage terms
            LAST_PRICE        float Price of the last trade
            VOLUME            float Daily volume
            HIGH              float Daily high
            LOW               float Daily low
            ================= ===== ================================================================

        Examples
        --------
         ::

            bfx_client.tickers(['tIOTUSD', 'fIOT'])
            bfx_client.tickers(['tBTCUSD'])
            bfx_client.tickers(['ALL'])

        """
        assert isinstance(symbol_list, list), "symbol_list must be of type list"
        assert symbol_list, "symbol_list must have at least one symbol"
        path = "v2/tickers?symbols={}".format(",".join(symbol_list))
        response = self._get(path)
        return response

    def ticker(self, symbol):
        """`Bitfinex ticker reference
        <https://bitfinex.readme.io/v2/reference#rest-public-ticker>`_

        The ticker is a high level overview of the state of the market.It shows you the current best
        bid and ask, as well as the last trade price.It also includes information such as daily
        volume and how much the price has moved over the last day.

        Parameters
        ----------
        symbol : str
            The symbol you want information about.
            You can find the list of valid symbols by calling the `symbols <restv1.html#symbols>`_
            method

        Returns
        -------
        list
             ::

                # on trading pairs (ex. tBTCUSD)
                [
                  BID,
                  BID_SIZE,
                  ASK,
                  ASK_SIZE,
                  DAILY_CHANGE,
                  DAILY_CHANGE_PERC,
                  LAST_PRICE,
                  VOLUME,
                  HIGH,
                  LOW
                ]
                # on funding currencies (ex. fUSD)
                [
                  FRR,
                  BID,
                  BID_SIZE,
                  BID_PERIOD,
                  ASK,
                  ASK_SIZE,
                  ASK_PERIOD,
                  DAILY_CHANGE,
                  DAILY_CHANGE_PERC,
                  LAST_PRICE,
                  VOLUME,
                  HIGH,
                  LOW
                ]

        Examples
        --------
         ::

            bfx_client.ticker('tIOTUSD')
            bfx_client.ticker('fIOT')
            bfx_client.ticker('tBTCUSD')

        """
        path = "v2/ticker/{}".format(symbol)
        response = self._get(path)
        return response

    def trades(self, symbol):
        """`Bitfinex trades reference
        <https://bitfinex.readme.io/v2/reference#rest-public-trades>`_

        Trades endpoint includes all the pertinent details of the trade, such as price,
        size and time.

        Parameters
        ----------
        symbol : str
            The symbol you want information about.
            You can find the list of valid symbols by calling the `symbols <restv1.html#symbols>`_
            method

        Returns
        -------
        list
             ::

                # on trading pairs (ex. tBTCUSD)
                [
                  [
                    ID,
                    MTS,
                    AMOUNT,
                    PRICE
                  ]
                ]
                # on funding currencies (ex. fUSD)
                [
                  [
                    ID,
                    MTS,
                    AMOUNT,
                    RATE,
                    PERIOD
                  ]
                ]

        Examples
        --------
         ::

            bfx_client.trades('tIOTUSD')
            bfx_client.trades('fIOT')
            bfx_client.trades('tBTCUSD')

        """
        path = "v2/trades/{}/hist".format(symbol)
        response = self._get(path)
        return response

    def books(self, symbol, precision="P0"):
        """`Bitfinex books reference
        <https://bitfinex.readme.io/v2/reference#rest-public-books>`_

        The Order Books channel allow you to keep track of the state of the Bitfinex order book.
        It is provided on a price aggregated basis, with customizable precision.

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        precision : Optional str
            Level of price aggregation (P0, P1, P2, P3, R0).
            R0 means "gets the raw orderbook".

        Returns
        -------
        list
             ::

                # on trading pairs (ex. tBTCUSD)
                [
                  [
                    PRICE,
                    COUNT,
                    AMOUNT
                  ]
                ]
                # on funding currencies (ex. fUSD)
                [
                  [
                    RATE,
                    PERIOD,
                    COUNT,
                    AMOUNT
                  ]
                ]

        Examples
        --------
         ::

            bfx_client.books('tIOTUSD')
            bfx_client.books('fIOT')
            bfx_client.books('tBTCUSD')

        """
        path = "v2/book/{}/{}".format(symbol, precision)
        response = self._get(path)
        return response

    def stats(self, **kwargs):
        """`Bitfinex stats reference
        <https://bitfinex.readme.io/v2/reference#rest-public-stats>`_

        Various statistics about the requested pair.

        Parameters
        ----------
        Key : str
            Allowed values: "funding.size", "credits.size", "credits.size.sym",
            "pos.size"

        Size : str
            Available values: '1m'

        Symbol : str
            The symbol you want information about.

        Symbol2 : str
            The symbol you want information about.

        Side : str
            Available values: "long", "short"

        Section : str
            Available values: "last", "hist"

        sort : str
            if = 1 it sorts results returned with old > new

        Returns
        -------
        list
             ::

                # response with Section = "last"
                [
                  MTS,
                  VALUE
                ]
                # response with Section = "hist"
                [
                  [ MTS, VALUE ],
                  ...
                ]

        Examples
        --------
         ::

            PARAMS = {
                'key': 'funding.size',
                'size': '1m',
                'symbol': 'fUSD',
                'section': 'hist',
                'sort': '0'
            }
            bfx_client.stats(**PARAMS)              # statistics

            PARAMS = {
                'key': 'credits.size',
                'size': '1m',
                'symbol': 'fUSD',
                'section': 'hist',
                'sort': '0'
            }
            bfx_client.stats(**PARAMS)              # statistics

            PARAMS = {
                'key': 'pos.size',
                'size': '1m',
                'symbol': 'tIOTUSD',
                'side': 'short',
                'section': 'hist',
                'sort': '0'
            }
            bfx_client.stats(**PARAMS)              # statistics

            PARAMS = {
                'key': 'credits.size.sym',
                'size': '1m',
                'symbol': 'fUSD',
                'symbol2': 'tBTCUSD',
                'section': 'hist',
                'sort': '0'
            }

        """
        key_values = ['funding.size', 'credits.size', 'credits.size.sym', 'pos.size']
        if kwargs['key'] not in key_values:
            key_values = " ".join(key_values)
            msg = "Key must have one of the following values : {}".format(key_values)
            raise ValueError(msg)

        common_stats_url = "v2/stats1/{}:{}:{}".format(
            kwargs['key'],
            kwargs['size'],
            kwargs['symbol']
        )

        if kwargs['key'] == 'pos.size':
            custom_stats_url = ":{}/{}?sort={}".format(
                kwargs['side'],
                kwargs['section'],
                str(kwargs['sort'])
            )

        if kwargs['key'] in ['funding.size', 'credits.size']:
            custom_stats_url = "/{}?sort={}".format(
                kwargs['section'],
                str(kwargs['sort'])
            )

        if kwargs['key'] == 'credits.size.sym':
            custom_stats_url = ":{}/{}?sort={}".format(
                kwargs['symbol2'],
                kwargs['section'],
                str(kwargs['sort'])
            )

        path = "".join([common_stats_url, custom_stats_url])

        response = self._get(path)
        return response

    def candles(self, *args, **kwargs):
        """`Bitfinex candles reference
        <https://bitfinex.readme.io/v2/reference#rest-public-candles>`_

        Provides a way to access charting candle info

        Parameters
        ----------
        timeFrame : str
            Available values: '1m', '5m', '15m', '30m', '1h', '3h', '6h', '12h',
            '1D', '7D', '14D', '1M'

        symbol : str
            The symbol you want information about.

        section : str
            Available values: "last", "hist"

        limit : int
            Number of candles requested

        start : str
            Filter start (ms)

        end : str
            Filter end (ms)

        sort : int
            if = 1 it sorts results returned with old > new

        Returns
        -------
        list
             ::

                # response with Section = "last"
                [
                  MTS,
                  OPEN,
                  CLOSE,
                  HIGH,
                  LOW,
                  VOLUME
                ]

                # response with Section = "hist"
                [
                  [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ],
                  ...
                ]

        Examples
        --------
         ::

            # 1 minute candles
            bfx_client.candles("1m", "tBTCUSD", "hist")

            # 1 hour candles , limit to 1 candle
            bfx_client.candles("1h", "tBTCUSD", "hist", limit='1')
            bfx_client.candles("1h", "tBTCUSD", "last")

        """
        margs = list(args)
        section = margs.pop()
        path = "v2/candles/trade"
        for arg in margs:
            path = path + ":" + arg
        path += "/{}".format(section)
        response = self._get(path, **kwargs)
        return response

    # REST CALCULATION ENDPOINTS
    def market_average_price(self, **kwargs):
        """`Bitfinex market average price reference
        <https://bitfinex.readme.io/v2/reference#rest-calc-market-average-price>`_

        Calculate the average execution rate for Trading or Margin funding.

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        amount : str
            Amount. Positive for buy, negative for sell (ex. "1.123")

        period : Optional int
            Maximum period for Margin Funding

        rate_limit : str
            Limit rate/price (ex. "1000.5")

        Returns
        -------
        list
             ::

                [RATE_AVG, AMOUNT]

        Example
        -------
         ::

            bfx_client.market_average_price(symbol="tBTCUSD", amount="100", period="1m")

        """
        body = kwargs
        raw_body = json.dumps(body)
        path = "v2/calc/trade/avg"
        response = self._post(path, raw_body, verify=True)
        return response

    def foreign_exchange_rate(self, **kwargs):
        """`Bitfinex foreign exchange rate reference
        <https://bitfinex.readme.io/v2/reference#foreign-exchange-rate>`_


        Parameters
        ----------
        ccy1 : str
            First currency

        ccy2 : str
            Second currency

        Returns
        -------
        list
             ::

                [ CURRENT_RATE ]

        Example
        -------
         ::

            bfx_client.foreign_exchange_rate(ccy1="IOT", ccy2="USD")

        """
        body = kwargs
        raw_body = json.dumps(body)
        path = "v2/calc/fx"
        response = self._post(path, raw_body, verify=True)
        return response

    # REST AUTHENTICATED ENDPOINTS
    def wallets_balance(self):
        """`Bitfinex wallets balance reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-wallets>`_

        Get account wallets

        Returns
        -------
        list
             ::

                [
                  [
                    WALLET_TYPE,
                    CURRENCY,
                    BALANCE,
                    UNSETTLED_INTEREST,
                    BALANCE_AVAILABLE,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.wallets_balance()

        """

        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/wallets"
        response = self._post(path, raw_body, verify=True)
        return response

    def active_orders(self, trade_pair=""):
        """`Bitfinex active orders reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-orders>`_

        Fetch active orders using rest api v2

        Parameters
        ----------
        symbol : Optional str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    GID,
                    CID,
                    SYMBOL,
                    MTS_CREATE,
                    MTS_UPDATE,
                    AMOUNT,
                    AMOUNT_ORIG,
                    TYPE,
                    TYPE_PREV,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    FLAGS,
                    STATUS,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    PRICE,
                    PRICE_AVG,
                    PRICE_TRAILING,
                    PRICE_AUX_LIMIT,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    HIDDEN,
                    PLACED_ID,
                    ...
                  ],
                  ...
                ]

        Examples
        --------
         ::

            bfx_client.active_orders("tIOTUSD")
            bfx_client.active_orders()

        """

        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/orders/{}".format(trade_pair)
        response = self._post(path, raw_body, verify=True)
        return response

    def orders_history(self, trade_pair, **kwargs):
        """`Bitfinex orders history reference
        <https://bitfinex.readme.io/v2/reference#orders-history>`_

        Returns the most recent closed or canceled orders up to circa two weeks ago

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        start : Optional int
            Millisecond start time

        end : Optional int
            Millisecond end time

        limit : Optional int
            Number of records

        sort : Optional int
            set to 1 to get results in ascending order or -1 for descending

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    GID,
                    CID,
                    SYMBOL,
                    MTS_CREATE,
                    MTS_UPDATE,
                    AMOUNT,
                    AMOUNT_ORIG,
                    TYPE,
                    TYPE_PREV,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    FLAGS,
                    STATUS,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    PRICE,
                    PRICE_AVG,
                    PRICE_TRAILING,
                    PRICE_AUX_LIMIT,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    NOTIFY,
                    HIDDEN,
                    PLACED_ID,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.orders_history("tIOTUSD")

        """

        body = kwargs
        raw_body = json.dumps(body)
        path = "v2/auth/r/orders/{}/hist".format(trade_pair)
        response = self._post(path, raw_body, verify=True)
        return response

    def order_trades(self, trade_pair, order_id):
        """`Bitfinex order trades reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-order-trades>`_

        Get Trades generated by an Order

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        orderid : int
            Order id

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    PAIR,
                    MTS_CREATE,
                    ORDER_ID,
                    EXEC_AMOUNT,
                    EXEC_PRICE,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    MAKER,
                    FEE,
                    FEE_CURRENCY,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.order_trades("tIOTUSD", 14395751815)

        """
        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/order/{}:{}/trades".format(trade_pair, order_id)
        response = self._post(path, raw_body, verify=True)
        return response

    def trades_history(self, trade_pair=None, **kwargs):
        """`Bitfinex trades history reference
        <https://docs.bitfinex.com/v2/reference#rest-auth-trades-hist>`_

        List of trades

        Parameters
        ----------
        trade_pair : Optional str
            The `symbol <restv1.html#symbols>`_ you want information about.
            Omit for all symbols

        start : Optional int
            Millisecond start time

        end : Optional int
            Millisecond end time

        limit : Optional int
            Number of records

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    PAIR,
                    MTS_CREATE,
                    ORDER_ID,
                    EXEC_AMOUNT,
                    EXEC_PRICE,
                    ORDER_TYPE,
                    ORDER_PRICE,
                    MAKER,
                    FEE,
                    FEE_CURRENCY,
                    ...
                  ],
                  ...
                ]

        Examples
        --------
         ::

            bfx_client.trades_history('tIOTUSD', limit=10)

            TH = BTFXCLIENT.trades_history("tIOTUSD")
            for trade in TH:
                print(trade)

        """

        body = kwargs
        raw_body = json.dumps(body)
        if trade_pair is None:
            path = "v2/auth/r/trades/hist"  # will load history for all pairs
        else:
            path = "v2/auth/r/trades/{}/hist".format(trade_pair)
        response = self._post(path, raw_body, verify=True)
        return response

    def active_positions(self):
        """`Bitfinex positions reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-positions>`_

        Get active positions

        Returns
        -------
        list
             ::

                [
                  [
                    SYMBOL,
                    STATUS,
                    AMOUNT,
                    BASE_PRICE,
                    MARGIN_FUNDING,
                    MARGIN_FUNDING_TYPE,
                    PL,
                    PL_PERC,
                    PRICE_LIQ,
                    LEVERAGE
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.active_positions()

        """
        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/positions"
        response = self._post(path, raw_body, verify=True)
        return response

    def positions_history(self, **kwargs):
        """`Bitfinex positions history reference
        <https://docs.bitfinex.com/v2/reference#positions-history>`_

        Return the positions of a user between two dates

        Parameters
        ----------
        start : Optional int
            Millisecond start time

        end : Optional int
            Millisecond end time

        limit : Optional int
            Number of records

        Returns
        -------
        list
             ::

                [
                  [
                    SYMBOL,
                    STATUS,
                    AMOUNT,
                    BASE_PRICE,
                    MARGIN_FUNDING,
                    MARGIN_FUNDING_TYPE,
                    PL,
                    PL_PERC,
                    PRICE_LIQ,
                    LEVERAGE,
                    ID,
                    MTS_CREATE,
                    MTS_UPDATE
                  ],
                  ...
                ]

        Examples
        --------
         ::

            positions = bfx_client.positions_history(limit=10)
            for position in positions:
                print(position)

        """

        body = kwargs
        raw_body = json.dumps(body)
        path = "v2/auth/r/positions/hist"
        response = self._post(path, raw_body, verify=True)
        return response

    def positions_audit(self, **kwargs):
        """`Bitfinex positions audit reference
        <https://docs.bitfinex.com/v2/reference#positions-audit>`_

        Return and audit of the positions of a user that correspond to the ids send

        Parameters
        ----------
        id : Optional list of ints
            List of position IDs to audit

        start : Optional int
            Millisecond start time

        end : Optional int
            Millisecond end time

        limit : Optional int
            Number of records

        Returns
        -------
        list
             ::

                [
                  [
                    SYMBOL,
                    STATUS,
                    AMOUNT,
                    BASE_PRICE,
                    MARGIN_FUNDING,
                    MARGIN_FUNDING_TYPE,
                    PL,
                    PL_PERC,
                    PRICE_LIQ,
                    LEVERAGE,
                    ID,
                    MTS_CREATE,
                    MTS_UPDATE,
                    TYPE,
                    COLLATERAL,
                    COLLATERAL_MIN,
                    META
                  ],
                  ...
                ]

        Examples
        --------
         ::

            positions = bfx_client.positions_audit([1, 2, 3])
            for position in positions:
                print(position)

        """

        body = kwargs
        raw_body = json.dumps(body)
        path = "v2/auth/r/positions/audit"
        response = self._post(path, raw_body, verify=True)
        return response

    def funding_offers(self, symbol=""):
        """`Bitfinex funding offers reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-funding-offers>`_

        Get active funding offers.

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    SYMBOL,
                    MTS_CREATED,
                    MTS_UPDATED,
                    AMOUNT,
                    AMOUNT_ORIG,
                    TYPE,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    FLAGS,
                    STATUS,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    RATE,
                    PERIOD,
                    NOTIFY,
                    HIDDEN,
                    _PLACEHOLDER,
                    RENEW,
                    ...
                  ],
                  ...
                ]

        Examples
        --------
         ::

            bfx_client.funding_offers()

            bfx_client.funding_offers("fIOT")

        """
        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/funding/offers/{}".format(symbol)
        response = self._post(path, raw_body, verify=True)
        return response

    def funding_offers_history(self, symbol="", **kwargs):
        """`Bitfinex funding offers hist reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-funding-offers-hist>`_

        Get past inactive funding offers. Limited to last 3 days.

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        start : Optional int
            Millisecond start time

        end : Optional int
            Millisecond end time

        limit : Optional int
            Number of records

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    SYMBOL,
                    MTS_CREATED,
                    MTS_UPDATED,
                    AMOUNT,
                    AMOUNT_ORIG,
                    TYPE,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    FLAGS,
                    STATUS,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    RATE,
                    PERIOD,
                    NOTIFY,
                    HIDDEN,
                    _PLACEHOLDER,
                    RENEW,
                    ...
                  ],
                  ...
                ]

        Examples
        --------
         ::

            bfx_client.funding_offers_history()

            bfx_client.funding_offers_history('fOMG')

        """
        body = kwargs
        raw_body = json.dumps(body)
        add_symbol = "{}/".format(symbol) if symbol else ""
        path = "v2/auth/r/funding/offers/{}hist".format(add_symbol)
        response = self._post(path, raw_body, verify=True)
        return response

    def funding_loans(self, symbol=""):
        """`Bitfinex funding loans reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-funding-loans>`_

        Funds not used in active positions

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    SYMBOL,
                    SIDE,
                    MTS_CREATE,
                    MTS_UPDATE,
                    AMOUNT,
                    FLAGS,
                    STATUS,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    RATE,
                    PERIOD,
                    MTS_OPENING,
                    MTS_LAST_PAYOUT,
                    NOTIFY,
                    HIDDEN,
                    _PLACEHOLDER,
                    RENEW,
                    _PLACEHOLDER,
                    NO_CLOSE,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.funding_loans('fOMG')

        """
        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/funding/loans/{}".format(symbol)
        response = self._post(path, raw_body, verify=True)
        return response

    def funding_loans_history(self, symbol="", **kwargs):
        """`Bitfinex funding loans history reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-funding-loans-hist>`_

        Inactive funds not used in positions. Limited to last 3 days.

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        start : Optional int
            Millisecond start time

        end : Optional int
            Millisecond end time

        limit : Optional int
            Number of records

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    SYMBOL,
                    SIDE,
                    MTS_CREATE,
                    MTS_UPDATE,
                    AMOUNT,
                    FLAGS,
                    STATUS,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    RATE,
                    PERIOD,
                    MTS_OPENING,
                    MTS_LAST_PAYOUT,
                    NOTIFY,
                    HIDDEN,
                    _PLACEHOLDER,
                    RENEW,
                    _PLACEHOLDER,
                    NO_CLOSE,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.funding_loans_history('fOMG')

        """
        body = kwargs
        raw_body = json.dumps(body)
        add_symbol = "{}/".format(symbol) if symbol else ""
        path = "v2/auth/r/funding/loans/{}hist".format(add_symbol)
        response = self._post(path, raw_body, verify=True)
        return response

    def funding_credits(self, symbol=""):
        """`Bitfinex funding credits reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-funding-credits>`_

        Funds used in active positions

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    SYMBOL,
                    SIDE,
                    MTS_CREATE,
                    MTS_UPDATE,
                    AMOUNT,
                    FLAGS,
                    STATUS,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    RATE,
                    PERIOD,
                    MTS_OPENING,
                    MTS_LAST_PAYOUT,
                    NOTIFY,
                    HIDDEN,
                    _PLACEHOLDER,
                    RENEW,
                    _PLACEHOLDER,
                    NO_CLOSE,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.funding_credits('fUSD')

        """
        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/funding/credits/{}".format(symbol)
        response = self._post(path, raw_body, verify=True)
        return response

    def funding_credits_history(self, symbol="", **kwargs):
        """`Bitfinex funding credits history reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-funding-credits-hist>`_

        Inactive funds used in positions. Limited to last 3 days.

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        start : Optional int
            Millisecond start time

        end : Optional int
            Millisecond end time

        limit : Optional int
            Number of records

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    SYMBOL,
                    SYMBOL,
                    MTS_CREATE,
                    MTS_UPDATE,
                    AMOUNT,
                    FLAGS,
                    STATUS,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    _PLACEHOLDER,
                    RATE,
                    PERIOD,
                    MTS_OPENING,
                    MTS_LAST_PAYOUT,
                    NOTIFY,
                    HIDDEN,
                    _PLACEHOLDER,
                    RENEW,
                    _PLACEHOLDER,
                    NO_CLOSE,
                    POSITION_PAIR,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.funding_credits_history('fUSD')

        """
        body = kwargs
        raw_body = json.dumps(body)
        add_symbol = "{}/".format(symbol) if symbol else ""
        path = "v2/auth/r/funding/credits/{}hist".format(add_symbol)
        response = self._post(path, raw_body, verify=True)
        return response

    def funding_trades(self, symbol="", **kwargs):
        """`Bitfinex funding trades hitory reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-funding-trades-hist>`_

        Get funding trades

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        start : Optional int
            Millisecond start time

        end : Optional int
            Millisecond end time

        limit : Optional int
            Number of records

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    CURRENCY,
                    MTS_CREATE,
                    OFFER_ID,
                    AMOUNT,
                    RATE,
                    PERIOD,
                    MAKER,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.funding_trades('fUSD')

        """
        body = kwargs
        raw_body = json.dumps(body)
        add_symbol = "{}/".format(symbol) if symbol else ""
        path = "v2/auth/r/funding/trades/{}hist".format(add_symbol)
        response = self._post(path, raw_body, verify=True)
        return response

    def margin_info(self, tradepair="base"):
        """`Bitfinex margin info reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-info-margin>`_

        Get account margin info

        Parameters
        ----------
        key : str
            "base" | SYMBOL

        Returns
        -------
        list
             ::

                # margin base
                [
                  "base",
                  [
                    USER_PL,
                    USER_SWAPS,
                    MARGIN_BALANCE,
                    MARGIN_NET,
                    ...
                  ]
                ]

                # margin symbol
                [
                  SYMBOL,
                  [
                    TRADABLE_BALANCE,
                    GROSS_BALANCE,
                    BUY,
                    SELL,
                    ...
                  ]
                ]

        Examples
        --------
         ::

            bfx_client.margin_info()

            bfx_client.margin_info('base')

            bfx_client.margin_info('tIOTUSD')

        """
        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/info/margin/{}".format(tradepair)
        response = self._post(path, raw_body, verify=True)
        return response

    def funding_info(self, tradepair):
        """`Bitfinex funding info reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-info-funding>`_

        Get account funding info

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        list
             ::

                [
                  "sym",
                  SYMBOL,
                  [
                    YIELD_LOAN,
                    YIELD_LEND,
                    DURATION_LOAN,
                    DURATION_LEND,
                    ...
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.funding_info('fIOT')

        """
        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/info/funding/{}".format(tradepair)
        response = self._post(path, raw_body, verify=True)
        return response

    def movements(self, currency=""):
        """`Bitfinex movements reference
        <https://bitfinex.readme.io/v2/reference#movements>`_

        View your past deposits/withdrawals.

        Parameters
        ----------
        Currency : str
            Currency (BTC, ...)

        Returns
        -------
        list
             ::

                [
                  [
                    ID,
                    CURRENCY,
                    CURRENCY_NAME,
                    null,
                    null,
                    MTS_STARTED,
                    MTS_UPDATED,
                    null,
                    null,
                    STATUS,
                    null,
                    null,
                    AMOUNT,
                    FEES,
                    null,
                    null,
                    DESTINATION_ADDRESS,
                    null,
                    null,
                    null,
                    TRANSACTION_ID,
                    null
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.movements()

            bfx_client.movements("BTC")

        """
        body = {}
        raw_body = json.dumps(body)
        add_currency = "{}/".format(currency.upper()) if currency else ""
        path = "v2/auth/r/movements/{}hist".format(add_currency)
        response = self._post(path, raw_body, verify=True)
        return response

    def performance(self, period="1D"):
        """`Bitfinex performance reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-performance>`_

        Get account historical daily performance (work in progress on Bitfinex side)

        This endpoint is still under active development so you might experience unexpected behavior
        from it.

        Currently not working : bitfinex.rest.restv2.BitfinexException:
        (500, 'Internal Server Error', ['error', 10020, 'method: invalid'])

        Returns
        -------
        list
            The list contains the following information::

                [ CURRENT_RATE ]

        Example
        -------
         ::

            bfx_client.performance()

        """
        body = {}
        raw_body = json.dumps(body)
        path = "v2/auth/r/stats/perf:{}/hist".format(period)
        response = self._post(path, raw_body, verify=True)
        return response

    def alert_list(self):
        """`Bitfinex list alerts reference
        <https://docs.bitfinex.com/v2/reference#rest-auth-alert-list>`_

        List of active alerts

        Returns
        -------
        list
             ::

                [
                  [
                    'price:tBTCUSD:560.92',
                    'price',
                    'tBTCUSD',
                    560.92,
                    91
                  ],
                  ...
                ]

        Example
        -------
         ::

            bfx_client.alert_list()

        """
        body = {'type': 'price'}
        raw_body = json.dumps(body)
        path = "v2/auth/r/alerts"
        response = self._post(path, raw_body, verify=True)
        return response

    def alert_set(self, alert_type, symbol, price):
        """`Bitfinex auth alert set reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-alert-set>`_

        Sets up a price alert at the given value

        Parameters
        ----------
        type : str
            Only one type is available : "price"

        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        price : float
            Price where you want to receive alerts

        Returns
        -------
        list
             ::

                [
                  'price:tBTCUSD:600',
                  'price',
                  'tBTCUSD',
                  600,
                  100
                ]

        Example
        -------
         ::

            bfx_client.alert_set('price', 'tIOTUSD', 3)

        """
        body = {
            'type': alert_type,
            'symbol': symbol,
            'price': price
        }

        raw_body = json.dumps(body)
        path = "v2/auth/w/alert/set"
        response = self._post(path, raw_body, verify=True)
        return response

    def alert_delete(self, symbol, price):
        """`Bitfinex auth alert delete reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-alert-delete>`_


        Bitfinex always returns [True] no matter if the request deleted an alert or not

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        price : float
            Price where you want to receive alerts

        Returns
        -------
        list
             ::

                [ True ]

        Example
        -------
         ::

            bfx_client.alert_delete('tIOTUSD', 1)

        """
        body = {}

        raw_body = json.dumps(body)
        path = "v2/auth/w/alert/price:{}:{}/del".format(symbol, price)
        response = self._post(path, raw_body, verify=True)
        return response

    def calc_available_balance(self, symbol, direction, rate, order_type):
        """`Bitfinex calc balance available reference
        <https://bitfinex.readme.io/v2/reference#rest-auth-calc-bal-avail>`_

        Calculate available balance for order/offer
        example : calc_available_balance("tIOTUSD","1","1.13","EXCHANGE")

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        dir : int
            direction of the order/offer
            (orders: > 0 buy, < 0 sell | offers: > 0 sell, < 0 buy)

        rate : string
            Rate of the order/offer

        type : string
            Type of the order/offer EXCHANGE or MARGIN

        Returns
        -------
        list
             ::

                [AMOUNT_AVAIL]

        Example
        -------
         ::

            bfx_client.calc_available_balance('tIOTUSD', 1, 0.02, 'EXCHANGE')

        """

        body = {
            'symbol': symbol,
            'dir': direction,
            'rate': rate,
            'type': order_type
        }

        raw_body = json.dumps(body)
        path = "v2/auth/calc/order/avail"
        response = self._post(path, raw_body, verify=True)
        return response

    def ledgers(self, currency=""):
        """`Bitfinex ledgers reference
        <https://bitfinex.readme.io/v2/reference#ledgers>`_

        View your past ledger entries.

        Parameters
        ----------
        Currency : str
            Currency (BTC, ...)

        Returns
        -------
        list
             ::

            [
              [
                ID,
                CURRENCY,
                null,
                TIMESTAMP_MILLI,
                null,
                AMOUNT,
                BALANCE,
                null,
                DESCRIPTION
              ],
              ...
            ]

        Example
        --------
         ::

            bfx_client.ledgers('IOT')

        """
        body = {}
        raw_body = json.dumps(body)
        add_currency = "{}/".format(currency.upper()) if currency else ""
        path = "v2/auth/r/ledgers/{}hist".format(add_currency)
        response = self._post(path, raw_body, verify=True)
        return response

    def user_settings_read(self, pkey):
        """`Bitfinex user settings read reference
        <https://bitfinex.readme.io/v2/reference#user-settings-read>`_

        Read user settings

        Parameters
        ----------
        pkey : str
            Requested Key

        Returns
        -------
        list
             ::

                [
                  [
                    KEY
                    VALUE
                  ],
                  ...
                ]

        Example
        --------
         ::

            none available

        """
        body = {
            'keys': ['api:{}'.format(pkey)]
        }
        raw_body = json.dumps(body)
        path = "v2/auth/r/settings"
        response = self._post(path, raw_body, verify=True)
        return response

    def user_settings_write(self, pkey):
        """`Bitfinex user settings write reference
        <https://bitfinex.readme.io/v2/reference#user-settings-write>`_

        Write user settings

        Warning
        -------
        Not Implemented

        """
        raise NotImplementedError

    def user_settings_delete(self, pkey):
        """`Bitfinex user settings delete reference
        <https://bitfinex.readme.io/v2/reference#user-settings-delete>`_

        Delete user settings

        Warning
        -------
        Not Implemented

        """
        raise NotImplementedError
