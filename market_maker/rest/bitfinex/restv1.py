#!/usr/bin/python
#-*- coding: utf-8 -*-

from __future__ import absolute_import
import json
from json.decoder import JSONDecodeError
import base64
import hmac
import hashlib
import requests
from market_maker.utils.bitfinex import utils

PROTOCOL = "https"
HOST = "api.bitfinex.com"
VERSION = "v1"

PATH_SYMBOLS = "symbols"
PATH_TICKER = "pubticker/%s"
PATH_TODAY = "today/%s"
PATH_STATS = "stats/%s"
PATH_LENDBOOK = "lendbook/%s"
PATH_ORDERBOOK = "book/%s"
PATH_KEYINFO = "key_info"

# HTTP request timeout in seconds
TIMEOUT = 5.0


class BitfinexException(Exception):
    pass


class Client:
    """
    Client for the bitfinex.com API.

    Link for official bitfinex documentation :

    `Bitfinex rest1 docs <https://docs.bitfinex.com/v1/docs>`_

    `Bitfinex rest1 reference <https://docs.bitfinex.com/v1/reference>`_

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

    def __init__(self, key=None, secret=None, nonce_multiplier=1000.0):
        assert isinstance(nonce_multiplier, float), "nonce_multiplier must be decimal"
        self.url = "%s://%s/%s" % (PROTOCOL, HOST, VERSION)
        self.base_url = "%s://%s/" % (PROTOCOL, HOST)
        self.key = key
        self.secret = secret
        self.nonce_multiplier = nonce_multiplier

    def server(self):
        return u"{0:s}://{1:s}/{2:s}".format(PROTOCOL, HOST, VERSION)

    def url_for(self, path, path_arg=None, parameters=None):

        # build the basic url
        url = "%s/%s" % (self.server(), path)

        # If there is a path_arh, interpolate it into the URL.
        # In this case the path that was provided will need to have string
        # interpolation characters in it, such as PATH_TICKER
        if path_arg:
            url = url % (path_arg)

        # Append any parameters to the URL.
        if parameters:
            url = "%s?%s" % (url, self._build_parameters(parameters))

        return url

    def _nonce(self):
        """Returns a nonce used in authentication.
        Nonce must be an increasing number, if the API key has been used
        earlier or other frameworks that have used higher numbers you might
        need to increase the nonce_multiplier."""
        return str(utils.get_nonce(self.nonce_multiplier))

    def _sign_payload(self, payload):
        j = json.dumps(payload)
        data = base64.standard_b64encode(j.encode('utf8'))

        hmc = hmac.new(self.secret.encode('utf8'), data, hashlib.sha384)
        signature = hmc.hexdigest()
        return {
            "X-BFX-APIKEY": self.key,
            "X-BFX-SIGNATURE": signature,
            "X-BFX-PAYLOAD": data
        }

    def _get(self, url):
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            return response.json()
        else:
            try:
                content = response.json()
            except JSONDecodeError:
                content = response.text()
            raise BitfinexException(response.status_code, response.reason, content)

    def _post(self, endoint, payload, verify=True):
        url = self.url_for(path=endoint)
        signed_payload = self._sign_payload(payload)
        response = requests.post(url, headers=signed_payload, verify=verify)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            return response.json()
        else:
            try:
                content = response.json()
            except JSONDecodeError:
                content = response.text()
            raise BitfinexException(response.status_code, response.reason, content)

    def _build_parameters(self, parameters):
        # sort the keys so we can test easily in Python 3.3 (dicts are not
        # ordered)
        keys = list(parameters.keys())
        keys.sort()

        return '&'.join(["%s=%s" % (k, parameters[k]) for k in keys])

    def place_order(self, amount, price, side, ord_type, symbol='btcusd', exchange='bitfinex'):
        """
        .. _new_order:

        `Bitfinex new order <https://docs.bitfinex.com/v1/reference#rest-auth-new-order>`_

        Submit a new Order

        Parameters
        ----------
        amount : float
            Order size: how much you want to buy or sell

        price : float
            Price to buy or sell at. Must be positive. Use random number for market orders.

        side : string
            Either “buy” or “sell”.

        ord_type : string
            Either “market” / “limit” / “stop” / “trailing-stop” / “fill-or-kill” /
            “exchange market” / “exchange limit” / “exchange stop” / “exchange trailing-stop” /
            “exchange fill-or-kill”. (type starting by “exchange ” are exchange orders, others are
            margin trading orders)

        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        exchange : str
            'bitfinex'

        Returns
        -------
        dict
             ::

                # response
                {
                  "id":448364249,
                  "symbol":"btcusd",
                  "exchange":"bitfinex",
                  "price":"0.01",
                  "avg_execution_price":"0.0",
                  "side":"buy",
                  "type":"exchange limit",
                  "timestamp":"1444272165.252370982",
                  "is_live":true,
                  "is_cancelled":false,
                  "is_hidden":false,
                  "was_forced":false,
                  "original_amount":"0.01",
                  "remaining_amount":"0.01",
                  "executed_amount":"0.0",
                  "order_id":448364249
                }

        Examples
        --------
         ::

            bfx_client.place_order(0.01, 0.01, "buy", "exchange limit", "btcusd")

        """

        payload = {

            "request": "/v1/order/new",
            "nonce": self._nonce(),
            "symbol": symbol,
            "amount": amount,
            "price": price,
            "exchange": exchange,
            "side": side,
            "type": ord_type

        }

        response = self._post("/order/new", payload=payload, verify=True)
        return response

    def place_multiple_orders(self, orders):
        """
        Parameters
        ----------
        orders : list
            Each item in the list is a dict that must have the following items : symbol, amount,
            price, side, type, exchange



        Returns
        -------
        dict
             ::

                // response
                {
                  "order_ids":[
                    {
                        "id":448383727,
                        "symbol":"btcusd",
                        "exchange":"bitfinex",
                        "price":"0.01",
                        "avg_execution_price":"0.0",
                        "side":"buy",
                        "type":"exchange limit",
                        "timestamp":"1444274013.621701916",
                        "is_live":true,
                        "is_cancelled":false,
                        "is_hidden":false,
                        "was_forced":false,
                        "original_amount":"0.01",
                        "remaining_amount":"0.01",
                        "executed_amount":"0.0"
                    },{
                        "id":448383729,
                        "symbol":"btcusd",
                        "exchange":"bitfinex",
                        "price":"0.03",
                        "avg_execution_price":"0.0",
                        "side":"buy",
                        "type":"exchange limit",
                        "timestamp":"1444274013.661297306",
                        "is_live":true,
                        "is_cancelled":false,
                        "is_hidden":false,
                        "was_forced":false,
                        "original_amount":"0.02",
                        "remaining_amount":"0.02",
                        "executed_amount":"0.0"
                    }],
                  "status":"success"
                }

        Examples
        --------
         ::

            # Make a list with 3 orders to buy 100 iota at 3 dollars,100 iota at 4 dollars and
            # 100 iota at 5 dollars
            # The list is sent to the method place_multiple_orders
            orders = []
            for price in range(3, 6):
                print(price)
                payload = {
                    "symbol": 'IOTUSD',
                    "amount": '100',
                    "price": str(price),
                    "exchange": 'bitfinex',
                    "side": 'buy',
                    "type": 'limit'
                }
                orders.append(payload)
            response = bfx_client.place_multiple_orders(orders)
            print(response)
        """

        payload = {
            "request": "/v1/order/new/multi",
            "nonce": self._nonce(),
            "orders": orders
        }
        response = self._post("/order/new/multi", payload=payload, verify=True)
        return response

    def delete_order(self, order_id):
        """`Bitfinex cancel order reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-cancel-order>`_

        Cancel an order.

        Parameters
        ----------
        order_id : int
            The order ID given by `new_order`_ function

        Returns
        -------
        dict
             ::

                {
                  "id":446915287,
                  "symbol":"btcusd",
                  "exchange":null,
                  "price":"239.0",
                  "avg_execution_price":"0.0",
                  "side":"sell",
                  "type":"trailing stop",
                  "timestamp":"1444141982.0",
                  "is_live":true,
                  "is_cancelled":false,
                  "is_hidden":false,
                  "was_forced":false,
                  "original_amount":"1.0",
                  "remaining_amount":"1.0",
                  "executed_amount":"0.0"
                }

        Example
        -------
         ::

            bfx_client.delete_order(448411153)

        """

        payload = {
            "request": "/v1/order/cancel",
            "nonce": self._nonce(),
            "order_id": order_id
        }

        response = self._post("/order/cancel", payload=payload, verify=True)
        return response

    def delete_multiple_orders(self, order_ids):
        """`Bitfinex cancel multiple orders reference
        <https://docs.bitfinex.com/reference#rest-auth-cancel-multiple-orders>`_

        Cancel multiple orders.

        Parameters
        ----------
        order_ids : []
            An array of the order IDs given by /order/new or /order/new/multi

        Returns
        -------
        Confirmation of cancellation of the orders.

        Example
        -------
         ::

            bfx_client.delete_multiple_orders([448411153,448411148])

        """

        payload = {
            "request": "/v1/order/cancel/multi",
            "nonce": self._nonce(),
            "order_ids": order_ids
        }

        response = self._post("/order/cancel/multi", payload=payload, verify=True)
        return response

    def delete_all_orders(self):
        """`Bitfinex cancel all orders reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-cancel-multiple-orders>`_

        Cancel all orders at once.

        Returns
        -------
        dict
             ::

                {"result":"Orders cancelled"}

        Example
        -------
         ::

            bfx_client.delete_all_orders()

        """
        payload = {
            "request": "/v1/order/cancel/all",
            "nonce": self._nonce(),
        }

        response = self._post("/order/cancel/all", payload=payload, verify=True)
        return response

    def status_order(self, order_id):
        """`Bitfinex status order reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-order-status>`_

        Get the status of an order. Is it active? Was it cancelled?
        To what extent has it been executed? etc.

        Parameters
        ----------
        order_id : int
            The order ID given by `new_order`_ function

        Returns
        -------
        dict
             ::

                {
                  "id":448411153,
                  "symbol":"btcusd",
                  "exchange":null,
                  "price":"0.01",
                  "avg_execution_price":"0.0",
                  "side":"buy",
                  "type":"exchange limit",
                  "timestamp":"1444276570.0",
                  "is_live":false,
                  "is_cancelled":true,
                  "is_hidden":false,
                  "oco_order":null,
                  "was_forced":false,
                  "original_amount":"0.01",
                  "remaining_amount":"0.01",
                  "executed_amount":"0.0"
                }

        Example
        -------
         ::

            bfx_client.status_order(448411153)

        """

        payload = {
            "request": "/v1/order/status",
            "nonce": self._nonce(),
            "order_id": order_id
        }

        response = self._post("/order/status", payload=payload, verify=True)
        return response

    def active_orders(self):
        """`Bitfinex active orders reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-active-orders>`_

        View your active orders.

        Returns
        -------
        list
             ::

                [{
                  "id":448411365,
                  "symbol":"btcusd",
                  "exchange":"bitfinex",
                  "price":"0.02",
                  "avg_execution_price":"0.0",
                  "side":"buy",
                  "type":"exchange limit",
                  "timestamp":"1444276597.0",
                  "is_live":true,
                  "is_cancelled":false,
                  "is_hidden":false,
                  "was_forced":false,
                  "original_amount":"0.02",
                  "remaining_amount":"0.02",
                  "executed_amount":"0.0"
                }]

        Example
        -------
         ::

            bfx_client.active_orders(448411153)

        """
        payload = {
            "request": "/v1/orders",
            "nonce": self._nonce()
        }
        response = self._post("orders", payload=payload, verify=True)
        return response

    def active_positions(self):
        """`Bitfinex active positions reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-active-positions>`_

        View your active positions.

        Returns
        -------
        list
             ::

                [{
                  "id":943715,
                  "symbol":"btcusd",
                  "status":"ACTIVE",
                  "base":"246.94",
                  "amount":"1.0",
                  "timestamp":"1444141857.0",
                  "swap":"0.0",
                  "pl":"-2.22042"
                }]

        Example
        -------
         ::

            bfx_client.active_positions(448411153)

        """
        payload = {
            "request": "/v1/positions",
            "nonce": self._nonce()
        }
        response = self._post("positions", payload=payload, verify=True)
        return response

    def claim_position(self, position_id):
        """`Bitfinex claim position reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-claim-position>`_

        A position can be claimed if: It is a long position: The amount in the last unit of the
        position pair that you have in your trading wallet AND/OR the realized profit of the
        position is greater or equal to the purchase amount of the position
        (base price * position amount) and the funds which need to be returned. For example, for a
        long BTCUSD position, you can claim the position if the amount of USD you have in the
        trading wallet is greater than the base price * the position amount and the funds used.
        It is a short position: The amount in the first unit of the position pair that you have in
        your trading wallet is greater or equal to the amount of the position and the margin
        funding used.

        Parameters
        ----------
        position_id : int
            The position ID

        Returns
        -------
        dict
             ::

                {
                  "id":943715,
                  "symbol":"btcusd",
                  "status":"ACTIVE",
                  "base":"246.94",
                  "amount":"1.0",
                  "timestamp":"1444141857.0",
                  "swap":"0.0",
                  "pl":"-2.2304"
                }

        Example
        -------
         ::

            bfx_client.claim_position(18411153)

        """
        payload = {
            "request": "/v1/position/claim",
            "nonce": self._nonce(),
            "position_id": position_id
        }
        response = self._post("position/claim", payload=payload, verify=True)
        return response

    def close_position(self, position_id):
        """`Bitfinex close position reference
        <https://docs.bitfinex.com/v1/reference#close-position>`_

        Closes the selected position with a market order.

        Parameters
        ----------
        position_id : int
            The position ID

        Returns
        -------
        dict
             ::

                {
                  "message": "",
                    "order": {},
                  "position": {}
                }

        Example
        -------
         ::

            bfx_client.close_position(18411153)

        """
        payload = {
            "request": "/v1/position/close",
            "nonce": self._nonce(),
            "position_id": position_id
        }
        response = self._post("position/close", payload=payload, verify=True)
        return response

    def past_trades(self, timestamp='0.0', symbol='btcusd'):
        """`Bitfinex past trades reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-past-trades>`_

        View your past trades.

        Parameters
        ----------
        timestamp : str
            Trades made before this timestamp won’t be returned.

        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        list
             ::

                [{
                  "price":"246.94",
                  "amount":"1.0",
                  "timestamp":"1444141857.0",
                  "exchange":"",
                  "type":"Buy",
                  "fee_currency":"USD",
                  "fee_amount":"-0.49388",
                  "tid":11970839,
                  "order_id":446913929
                }]

        Example
        -------
         ::

            bfx_client.past_trades('0.0','btcusd')
            bfx_client.past_trades()

        """

        payload = {
            "request": "/v1/mytrades",
            "nonce": self._nonce(),
            "symbol": symbol,
            "timestamp": timestamp
        }

        response = self._post("/mytrades", payload=payload, verify=True)
        return response

    def place_offer(self, currency, amount, rate, period, direction):
        """
        .. _new_offer:

        `Bitfinex place offer reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-new-offer>`_

        Submit a new Offer

        Parameters
        ----------
        currency : string
            The name of the currency.

        amount : float
            Order size: how much to lend or borrow.

        rate : float
            Rate to lend or borrow at. In percentage per 365 days. (Set to 0 for FRR).

        period : int
            Number of days of the funding contract (in days)

        direction : string
            Either “lend” or “loan”.

        Returns
        -------
        dict
             ::

                {
                  "id":13800585,
                  "currency":"USD",
                  "rate":"20.0",
                  "period":2,
                  "direction":"lend",
                  "timestamp":"1444279698.21175971",
                  "is_live":true,
                  "is_cancelled":false,
                  "original_amount":"50.0",
                  "remaining_amount":"50.0",
                  "executed_amount":"0.0",
                  "offer_id":13800585
                }

        Example
        -------
         ::

            bfx_client.place_offer("USD",50.0,20.0,2,"lend")

        """
        payload = {
            "request": "/v1/offer/new",
            "nonce": self._nonce(),
            "currency": currency,
            "amount": amount,
            "rate": rate,
            "period": period,
            "direction": direction
        }

        response = self._post("/offer/new", payload=payload, verify=True)
        return response

    def cancel_offer(self, offer_id):
        """`Bitfinex cancel offer reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-cancel-offer>`_

        Cancel an offer.

        Parameters
        ----------
        offer_id : int
            The offer ID given by `new_offer`_ function

        Returns
        -------
        dict
             ::

                {
                  "id":13800585,
                  "currency":"USD",
                  "rate":"20.0",
                  "period":2,
                  "direction":"lend",
                  "timestamp":"1444279698.0",
                  "is_live":true,
                  "is_cancelled":false,
                  "original_amount":"50.0",
                  "remaining_amount":"50.0",
                  "executed_amount":"0.0"
                }

        Example
        -------
         ::

            bfx_client.cancel_offer(1231153)

        """
        payload = {
            "request": "/v1/offer/cancel",
            "nonce": self._nonce(),
            "offer_id": offer_id
        }

        response = self._post("/offer/cancel", payload=payload, verify=True)
        return response

    def status_offer(self, offer_id):
        """`Bitfinex status offer reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-offer-status>`_

        Get the status of an offer. Is it active? Was it cancelled?
        To what extent has it been executed? etc.

        Parameters
        ----------
        offer_id : int
            The offer ID given by `new_offer`_ function

        Returns
        -------
        dict
             ::

                {
                  "id":13800585,
                  "currency":"USD",
                  "rate":"20.0",
                  "period":2,
                  "direction":"lend",
                  "timestamp":"1444279698.0",
                  "is_live":false,
                  "is_cancelled":true,
                  "original_amount":"50.0",
                  "remaining_amount":"50.0",
                  "executed_amount":"0.0"
                }

        Example
        -------
         ::

            bfx_client.status_offer(354352)

        """
        payload = {
            "request": "/v1/offer/status",
            "nonce": self._nonce(),
            "offer_id": offer_id
        }

        response = self._post("/offer/status", payload=payload, verify=True)
        return response

    def offers_history(self):
        """`Bitfinex offers history reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-offers-hist>`_

        View your latest inactive offers. Limited to last 3 days and 1 request per minute.

        Returns
        -------
        list
             ::

                [{
                  "id":13800719,
                  "currency":"USD",
                  "rate":"31.39",
                  "period":2,
                  "direction":"lend",
                  "timestamp":"1444280237.0",
                  "is_live":false,
                  "is_cancelled":true,
                  "original_amount":"50.0",
                  "remaining_amount":"50.0",
                  "executed_amount":"0.0"
                }]

        Example
        -------
         ::

            bfx_client.offers_history()

        """

        payload = {
            "request": "/v1/offers/hist",
            "nonce": self._nonce()
        }
        response = self._post("/offers/hist", payload=payload, verify=True)
        return response

    def active_offers(self):
        """`Bitfinex active offers reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-offers>`_

        View your active offers.

        Returns
        -------
        list
             ::

                [{
                  "id":13800719,
                  "currency":"USD",
                  "rate":"31.39",
                  "period":2,
                  "direction":"lend",
                  "timestamp":"1444280237.0",
                  "is_live":true,
                  "is_cancelled":false,
                  "original_amount":"50.0",
                  "remaining_amount":"50.0",
                  "executed_amount":"0.0"
                }]

        Example
        -------
         ::

            bfx_client.active_offers()

        """
        payload = {
            "request": "/v1/offers",
            "nonce": self._nonce()
        }

        response = self._post("/offers", payload=payload, verify=True)
        return response

    def balances(self):
        """`Bitfinex balances reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-wallet-balances>`_

        See your balances

        Returns
        -------
        list
             ::

                [
                    {"type":"deposit", "currency":"btc", "amount":"0.0", "available":"0.0"},
                    {"type":"deposit", "currency":"usd", "amount":"1.0", "available":"1.0"},
                    {"type":"exchange", "currency":"btc", "amount":"1", "available":"1"},
                    {"type":"exchange", "currency":"usd", "amount":"1", "available":"1"},
                    {"type":"trading", "currency":"btc", "amount":"1", "available":"1"},
                    {"type":"trading", "currency":"usd", "amount":"1", "available":"1"},
                ...
                ]

        Example
        -------
         ::

            bfx_client.balances()

        """
        payload = {
            "request": "/v1/balances",
            "nonce": self._nonce()
        }
        response = self._post("/balances", payload=payload, verify=True)
        return response

    def history(self, currency, since=0, until=9999999999, limit=500, wallet='exchange'):
        """`Bitfinex balance history reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-wallet-balances>`_

        View all of your balance ledger entries.


        Parameters
        ----------
        currency : str
            The currency to look for.

        since : Optional str
            Return only the history after this timestamp. (Max 3 months before until)

        until : Optional str
            Return only the history before this timestamp. (Default now)

        limit : Optional int
            Limit the number of entries to return.

        wallet : Optional str
            Return only entries that took place in this wallet.
            Accepted inputs are: “trading”, “exchange”, “deposit”.

        Returns
        -------
        list
             ::

                [{
                  "currency":"USD",
                  "amount":"-246.94",
                  "balance":"515.4476526",
                  "description":"Position claimed @ 245.2 on wallet trading",
                  "timestamp":"1444277602.0"
                }]

        Example
        -------
         ::

            bfx_client.history('USD')

        """
        payload = {
            "request": "/v1/history",
            "nonce": self._nonce(),
            "currency": currency,
            "since": since,
            "until": until,
            "limit": limit,
            "wallet": wallet
        }
        response = self._post("/history", payload=payload, verify=True)
        return response

    def movements(self, currency, start=0, end=9999999999, limit=10000, method='bitcoin'):
        """`Bitfinex Deposit-Withdrawal History reference
        <https://docs.bitfinex.com/v1/reference#rest-auth-wallet-balances>`_

        View your past deposits/withdrawals.

        Parameters
        ----------
        currency : str
            The currency to look for.

        start : Optional str
            Return only the history after this timestamp. (Max 3 months before until)

        end : Optional str
            Return only the history before this timestamp. (Default now)

        limit : Optional int
            Limit the number of entries to return.

        method : str
            The method of the deposit/withdrawal (can be "bitcoin", "litecoin", "iota", "wire").

        Returns
        -------
        list
             ::

                [{
                  "id":581183,
                  "txid": 123456,
                  "currency":"BTC",
                  "method":"BITCOIN",
                  "type":"WITHDRAWAL",
                  "amount":".01",
                  "description":"3QXYWgRGX2BPYBpUDBssGbeWEa5zq6snBZ, offchain transfer ",
                  "address":"3QXYWgRGX2BPYBpUDBssGbeWEa5zq6snBZ",
                  "status":"COMPLETED",
                  "timestamp":"1443833327.0",
                  "timestamp_created": "1443833327.1",
                  "fee": 0.1
                }]

        Example
        -------
         ::

            bfx_client.movements('USD')

        """
        payload = {
            "request": "/v1/history/movements",
            "nonce": self._nonce(),
            "currency": currency,
            "since": start,
            "until": end,
            "limit": limit,
            "method": method
        }
        response = self._post("/history/movements", payload=payload, verify=True)
        return response

    def symbols(self):
        """
        .. _symbols:

        `Bitfinex symbols reference
        <https://docs.bitfinex.com/v1/reference#rest-public-symbols>`_

        A list of symbol names.

        Returns
        -------
        list
             ::

                [
                  "btcusd",
                  "ltcusd",
                  "ltcbtc",
                  ...
                ]

        Example
        -------
         ::

            bfx_client.symbols()

        """
        return self._get(self.url_for(PATH_SYMBOLS))

    def symbols_details(self):
        """`Bitfinex symbols details reference
        <https://docs.bitfinex.com/v1/reference#rest-public-symbol-details>`_

        Get a list of valid symbol IDs and the pair details.

        Returns
        -------
        list
             ::

                [{
                  "pair":"btcusd",
                  "price_precision":5,
                  "initial_margin":"30.0",
                  "minimum_margin":"15.0",
                  "maximum_order_size":"2000.0",
                  "minimum_order_size":"0.01",
                  "expiration":"NA"
                },{
                  "pair":"ltcusd",
                  "price_precision":5,
                  "initial_margin":"30.0",
                  "minimum_margin":"15.0",
                  "maximum_order_size":"5000.0",
                  "minimum_order_size":"0.1",
                  "expiration":"NA"
                },{
                  "pair":"ltcbtc",
                  "price_precision":5,
                  "initial_margin":"30.0",
                  "minimum_margin":"15.0",
                  "maximum_order_size":"5000.0",
                  "minimum_order_size":"0.1",
                  "expiration":"NA"
                },
                ...
                ]

        Example
        -------
         ::

            bfx_client.symbols_details()

        """
        return self._get(self.url_for("symbols_details"))

    def ticker(self, symbol):
        """`Bitfinex ticker reference
        <https://docs.bitfinex.com/v1/reference#rest-public-ticker>`_

        The ticker is a high level overview of the state of the market. It shows you the current
        best bid and ask, as well as the last trade price. It also includes information such as
        daily volume and how much the price has moved over the last day.

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        dict
             ::

                {
                  "mid":"244.755",
                  "bid":"244.75",
                  "ask":"244.76",
                  "last_price":"244.82",
                  "low":"244.2",
                  "high":"248.19",
                  "volume":"7842.11542563",
                  "timestamp":"1444253422.348340958"
                }

        Example
        -------
         ::

            bfx_client.ticker("BTCUSD")


        """

        return self._get(self.url_for(PATH_TICKER, (symbol)))

    def today(self, symbol):
        """.. _today:

        Get today stats

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        dict
             ::

                 {"low":"550.09","high":"572.2398","volume":"7305.33119836"}

        Example
        -------
         ::

            bfx_client.today("BTCUSD")

        """

        return self._get(self.url_for(PATH_TODAY, (symbol)))

    def stats(self, symbol):
        """`Bitfinex stats reference
        <https://docs.bitfinex.com/v1/reference#rest-public-stats>`_

        Various statistics about the requested pair.

        Parameters
        ----------
        symbol : str
            The `symbol <restv1.html#symbols>`_ you want information about.

        Returns
        -------
        dict
             ::

                [{
                  "period":1,
                  "volume":"7967.96766158"
                },{
                  "period":7,
                  "volume":"55938.67260266"
                },{
                  "period":30,
                  "volume":"275148.09653645"
                }]

        Example
        -------
         ::

            bfx_client.stats("BTCUSD")

        """
        data = self._get(self.url_for(PATH_STATS, (symbol)))

        for period in data:

            for key, value in period.items():
                if key == 'period':
                    new_value = int(value)
                elif key == 'volume':
                    new_value = value

                period[key] = new_value

        return data

    def lendbook(self, currency, parameters=None):
        """`Bitfinex Fundingbook reference
        <https://docs.bitfinex.com/v1/reference#rest-public-fundingbook>`_

        Get the full margin funding book

        Parameters
        ----------
        currency : str
            Currency

        Returns
        -------
        dict
             ::

                {
                  "bids":[{
                      'rate': '7.0482',
                      'amount': '244575.00836875',
                      'period': 30,
                      'timestamp': '1539157649.0',
                      'frr': False
                  }]
                  "asks":[{
                      'rate': '5.6831',
                      'amount': '63.5744',
                      'period': 2,
                      'timestamp':
                      '1539165059.0',
                      'frr': False
                  }]
                }

        Example
        -------
         ::

            bfx_client.lendbook("USD")

        """
        data = self._get(self.url_for(PATH_LENDBOOK, path_arg=currency, parameters=parameters))

        for lend_type in data.keys():

            for lend in data[lend_type]:

                for key, value in lend.items():
                    if key in ['rate', 'amount', 'timestamp']:
                        new_value = value
                    elif key == 'period':
                        new_value = int(value)
                    elif key == 'frr':
                        new_value = value == 'Yes'

                    lend[key] = new_value

        return data

    def order_book(self, symbol, parameters=None):
        """`Bitfinex Orderbook reference
        <https://docs.bitfinex.com/v1/reference#rest-public-orderbook>`_

        Get the full order book.

        Parameters
        ----------
        currency : str
            Currency

        Returns
        -------
        dict
             ::

                {
                  "bids":[{
                    "price":"574.61",
                    "amount":"0.1439327",
                    "timestamp":"1472506127.0"
                  }],
                  "asks":[{
                    "price":"574.62",
                    "amount":"19.1334",
                    "timestamp":"1472506126.0"
                  }]
                }

        Example
        -------
         ::

            bfx_client.order_book("BTCUSD")

        """
        data = self._get(self.url_for(PATH_ORDERBOOK, path_arg=symbol, parameters=parameters))

        for type_ in data.keys():
            for list_ in data[type_]:
                for key, value in list_.items():
                    list_[key] = value

        return data

    def key_permissions(self):
        """`Bitfinex API Key Permissions
        <https://docs.bitfinex.com/reference#auth-key-permissions>`_

        Check the permissions of the key being used to generate this request.

        Returns
        -------
        dict
             ::

                {
                    'account': {'read': True, 'write': False},
                    'history': {'read': True, 'write': False},
                    'orders': {'read': True, 'write': False},
                    'positions': {'read': True, 'write': False},
                    'funding': {'read': True, 'write': False},
                    'wallets': {'read': True, 'write': False},
                    'withdraw': {'read': False, 'write': False}
                }

        Example
        -------
         ::

            bfx_client.order_book("BTCUSD")

        """
        data = self._post(PATH_KEYINFO, {'request': '/v1/key_info', 'nonce': self._nonce()})

        return data


class TradeClient(Client):
    """Added for backward compatibility"""
    pass
