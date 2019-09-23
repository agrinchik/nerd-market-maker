"""
Module used to describe all of the different data types
"""

import time

STATUS_SUCCESS_API_V1 = "success"

class OrderType:
    """
    Enum used to describe all of the different order types available for use
    """
    MARKET = 'MARKET'
    LIMIT = 'LIMIT'
    STOP = 'STOP'
    STOP_LIMIT = 'STOP LIMIT'
    TRAILING_STOP = 'TRAILING STOP'
    FILL_OR_KILL = 'FOK'
    EXCHANGE_MARKET = 'EXCHANGE MARKET'
    EXCHANGE_LIMIT = 'EXCHANGE LIMIT'
    EXCHANGE_STOP = 'EXCHANGE STOP'
    EXCHANGE_STOP_LIMIT = 'EXCHANGE STOP LIMIT'
    EXCHANGE_TRAILING_STOP = 'EXCHANGE TRAILING STOP'
    EXCHANGE_FILL_OR_KILL = 'EXCHANGE FOK'


LIMIT_ORDERS = [OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.EXCHANGE_LIMIT,
                OrderType.EXCHANGE_STOP_LIMIT, OrderType.FILL_OR_KILL,
                OrderType.EXCHANGE_FILL_OR_KILL]


class OrderSide:
    """
    Enum used to describe the different directions of an order
    """
    BUY = 'buy'
    SELL = 'sell'


class OrderModelApiV1:
    ID = "id"
    GID = "gid"
    CID = "cid"
    SYMBOL = "symbol"
    MTS_CREATE = "timestamp"
    MTS_UPDATE = "timestamp"
    AMOUNT = "executed_amount"
    AMOUNT_REMAINING = "remaining_amount"
    AMOUNT_ORIG = "original_amount"
    SIDE = "side"
    TYPE = "type"
    PRICE = "price"
    PRICE_AVG = "avg_execution_price"
    IS_LIVE = "is_live"
    IS_CANCELED = "is_cancelled"


class OrderModelApiV2:
    """
    Enum used ad an index match to locate the different values in a
    raw order array
    """
    ID = 0
    GID = 1
    CID = 2
    SYMBOL = 3
    MTS_CREATE = 4
    MTS_UPDATE = 5
    AMOUNT = 6
    AMOUNT_ORIG = 7
    TYPE = 8
    TYPE_PREV = 9
    FLAGS = 12
    STATUS = 13
    PRICE = 16
    PRICE_AVG = 17
    PRICE_TRAILING = 18
    PRICE_AUX_LIMIT = 19
    NOTIFY = 23
    PLACE_ID = 25


class OrderFlags:
    """
    Enum used to explain the different values that can be passed in
    as flags
    """
    HIDDEN = 64
    CLOSE = 12
    REDUCE_ONLY = 1024
    POST_ONLY = 4096
    OCO = 16384


class OrderStatus:
    """
    Enum used to describe all of the different order statuses
    """
    ACTIVE = 'ACTIVE'
    EXECUTED = 'EXECUTED'
    PARTIALLY_FILLED = 'PARTIALLY FILLED'
    CANCELED = 'CANCELED'
    RSN_DUST = 'RSN_DUST'
    RSN_PAUSE = 'RSN_PAUSE'


def now_in_mills():
    """
    Gets the current time in milliseconds
    """
    return int(round(time.time() * 1000))


class Order:
    """
    ID	int64	Order ID
    GID	int	Group ID
    CID	int	Client Order ID
    SYMBOL	string	Pair (tBTCUSD, ...)
    MTS_CREATE	int	Millisecond timestamp of creation
    MTS_UPDATE	int	Millisecond timestamp of update
    AMOUNT	float	Positive means buy, negative means sell.
    AMOUNT_ORIG	float	Original amount
    TYPE	string	The type of the order: LIMIT, MARKET, STOP, TRAILING STOP,
      EXCHANGE MARKET, EXCHANGE LIMIT, EXCHANGE STOP, EXCHANGE TRAILING STOP, FOK, EXCHANGE FOK.
    TYPE_PREV	string	Previous order type
    FLAGS	int	Upcoming Params Object (stay tuned)
    ORDER_STATUS	string	Order Status: ACTIVE, EXECUTED, PARTIALLY FILLED, CANCELED
    PRICE	float	Price
    PRICE_AVG	float	Average price
    PRICE_TRAILING	float	The trailing price
    PRICE_AUX_LIMIT	float	Auxiliary Limit price (for STOP LIMIT)
    HIDDEN	int	1 if Hidden, 0 if not hidden
    PLACED_ID	int	If another order caused this order to be placed (OCO) this will be that other
    order's ID
    """

    Type = OrderType()
    Side = OrderSide()
    Flags = OrderFlags()

    def __init__(self):
        pass

    @staticmethod
    def from_raw_order_api_v1(raw_order):
        """
        Parse a raw order object into an Order oject

        @return order dict
        """
        return {
            "orderID": raw_order[OrderModelApiV1.ID],
            "clOrdID": raw_order[OrderModelApiV1.CID],
            # "clOrdLinkID": "string",
            # "account": 0,
            "symbol": raw_order[OrderModelApiV1.SYMBOL],
            "side": raw_order[OrderModelApiV1.SIDE].capitalize(),
            # "simpleOrderQty": 0,
            "orderQty": abs(float(raw_order[OrderModelApiV1.AMOUNT_ORIG])),
            "price": float(raw_order[OrderModelApiV1.PRICE]),
            # "displayQty": 0,
            # "stopPx": 0,
            # "pegOffsetValue": 0,
            # "pegPriceType": "string",
            # "currency": "string",
            # "settlCurrency": "string",
            "ordType": raw_order[OrderModelApiV1.TYPE],
            # "timeInForce": "string",
            # "execInst": "string",
            # "contingencyType": "string",
            # "exDestination": "string",
            "ordStatus": OrderStatus.EXECUTED if raw_order[OrderModelApiV1.IS_LIVE] is True else OrderStatus.CANCELED if raw_order[OrderModelApiV1.IS_CANCELED] is True else None,
            # "triggered": "string",
            # "workingIndicator": True,
            # "ordRejReason": "string",
            # "simpleLeavesQty": 0,
            "leavesQty": abs(float(raw_order[OrderModelApiV1.AMOUNT_REMAINING])),
            # "simpleCumQty": 0,
            "cumQty": abs(float(raw_order[OrderModelApiV1.AMOUNT])),
            # "avgPx": 0,
            # "multiLegReportingType": "string",
            # "text": "string",
            "transactTime": float(raw_order[OrderModelApiV1.MTS_CREATE]),
            "timestamp": float(raw_order[OrderModelApiV1.MTS_UPDATE])
        }

    @staticmethod
    def from_raw_order_api_v2(raw_order):
        """
        Parse a raw order object into an Order oject

        @return order dict
        """
        return {
            "orderID": raw_order[OrderModelApiV2.ID],
            "clOrdID": raw_order[OrderModelApiV2.CID],
            #"clOrdLinkID": "string",
            #"account": 0,
            "symbol": raw_order[OrderModelApiV2.SYMBOL],
            "side": ('Buy' if raw_order[OrderModelApiV2.AMOUNT_ORIG] > 0 else 'Sell'),
            #"simpleOrderQty": 0,
            "orderQty": abs(raw_order[OrderModelApiV2.AMOUNT_ORIG]),
            "price": raw_order[OrderModelApiV2.PRICE],
            #"displayQty": 0,
            #"stopPx": 0,
            #"pegOffsetValue": 0,
            #"pegPriceType": "string",
            #"currency": "string",
            #"settlCurrency": "string",
            "ordType": raw_order[OrderModelApiV2.TYPE],
            #"timeInForce": "string",
            #"execInst": "string",
            #"contingencyType": "string",
            #"exDestination": "string",
            "ordStatus": raw_order[OrderModelApiV2.STATUS],
            #"triggered": "string",
            #"workingIndicator": True,
            #"ordRejReason": "string",
            #"simpleLeavesQty": 0,
            "leavesQty": abs(raw_order[OrderModelApiV2.AMOUNT]),
            #"simpleCumQty": 0,
            "cumQty": abs(raw_order[OrderModelApiV2.AMOUNT_ORIG]) - abs(raw_order[OrderModelApiV2.AMOUNT]),
            #"avgPx": 0,
            #"multiLegReportingType": "string",
            #"text": "string",
            "transactTime": raw_order[OrderModelApiV2.MTS_CREATE],
            "timestamp": raw_order[OrderModelApiV2.MTS_UPDATE]
        }

    @staticmethod
    def get_order_status(order):
        status_str = order["ordStatus"]
        if OrderStatus.ACTIVE in status_str:
            return OrderStatus.ACTIVE
        if OrderStatus.EXECUTED in status_str:
            return OrderStatus.EXECUTED
        if OrderStatus.CANCELED in status_str:
            return OrderStatus.CANCELED
        if OrderStatus.RSN_DUST in status_str:
            return OrderStatus.RSN_DUST
        if OrderStatus.RSN_PAUSE in status_str:
            return OrderStatus.RSN_PAUSE

    @staticmethod
    def is_order_partially_filled(order):
        status_str = order["ordStatus"]
        if OrderStatus.PARTIALLY_FILLED in status_str:
            return True
        else:
            return False
