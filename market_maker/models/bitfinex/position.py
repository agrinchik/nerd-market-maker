"""
Module used to describe all of the different data types
"""


class PositionModel:
    """
    Enum used ad an index match to locate the different values in a
    raw order array
    """
    SYMBOL = 0
    STATUS = 1
    AMOUNT = 2
    BASE_PRICE = 3
    MARGIN_FUNDING = 4
    MARGIN_FUNDING_TYPE = 5
    PL = 6
    PL_PERC = 7
    PRICE_LIQ = 8
    LEVERAGE = 9
    ID = 11
    MTS_CREATE = 12
    MTS_UPDATE = 13
    TYPE = 15
    COLLATERAL = 17
    COLLATERAL_MIN = 18
    META = 19


class PositionStatus:
    """
    Enum used to describe all of the different position statuses
    """
    ACTIVE = 'ACTIVE'
    CLOSED = 'CLOSED'


class PositionTradeInfoReason:
    TRADE = 'TRADE'


class PositionTradeInfo:
    def __init__(self, meta_dict):
        self.reason = meta_dict["reason"] if meta_dict and meta_dict["reason"] else None
        self.trade_price = float(meta_dict["trade_price"]) if meta_dict and meta_dict["trade_price"] else None
        self.trade_amount = float(meta_dict["trade_amount"]) if meta_dict and meta_dict["trade_price"] else None

    def get_trade_side_str(self):
        result = ""
        if self.trade_amount and self.trade_amount > 0:
            result = "Buy"
        if self.trade_amount and self.trade_amount < 0:
            result = "Sell"
        return result


class Position:
    """
    SYMBOL	string	Pair (tBTCUSD, ...).
    STATUS	string	Status (ACTIVE, CLOSED).
    AMOUNT	float	Size of the position. Positive values means a long position,
            negative values means a short position.
    BASE_PRICE	float	The price at which you entered your position.
    MARGIN_FUNDING	float	The amount of funding being used for this position.
    MARGIN_FUNDING_TYPE	int	0 for daily, 1 for term.
    PL	float	Profit & Loss
    PL_PERC	float	Profit & Loss Percentage
    PRICE_LIQ	float	Liquidation price
    LEVERAGE	float	Beta value
    ID	int64	Position ID
    MTS_CREATE	int	Millisecond timestamp of creation
    MTS_UPDATE	int	Millisecond timestamp of update
    TYPE	string	The type of the position
    COLLATERAL string
    COLLATERAL_MIN string
    META json string Additional meta information about the position
    """

    def __init__(self):
        pass

    @staticmethod
    def get_list_value(data_list, index, default_value):
        result = data_list[index]
        if result is None:
            result = default_value
        return result

    @staticmethod
    def from_raw_position(raw_position):
        """
        Parse a raw position object into a Position object

        @return position dict
        """
        return {
            #"account": 0,
            "symbol": raw_position[PositionModel.SYMBOL],
            "status": raw_position[PositionModel.STATUS],
            #"currency": "string",
            #"underlying": "string",
            #"quoteCurrency": "string",
            #"commission": 0,
            #"initMarginReq": 0,
            #"maintMarginReq": 0,
            #"riskLimit": 0,
            "leverage": Position.get_list_value(raw_position, PositionModel.LEVERAGE, 0),
            "crossMargin": False,
            #"deleveragePercentile": 0,
            #"rebalancedPnl": 0,
            #"prevRealisedPnl": 0,
            #"prevUnrealisedPnl": 0,
            #"prevClosePrice": 0,
            "openingTimestamp": Position.get_list_value(raw_position, PositionModel.MTS_CREATE, 0),
            #"openingQty": 0,
            #"openingCost": 0,
            #"openingComm": 0,
            #"openOrderBuyQty": 0,
            #"openOrderBuyCost": 0,
            #"openOrderBuyPremium": 0,
            #"openOrderSellQty": 0,
            #"openOrderSellCost": 0,
            #"openOrderSellPremium": 0,
            #"execBuyQty": 0,
            #"execBuyCost": 0,
            #"execSellQty": 0,
            #"execSellCost": 0,
            #"execQty": 0,
            #"execCost": 0,
            #"execComm": 0,
            "currentTimestamp": Position.get_list_value(raw_position, PositionModel.MTS_UPDATE, 0),
            "currentQty": raw_position[PositionModel.AMOUNT],
            #"currentCost": 0,
            #"currentComm": 0,
            #"realisedCost": 0,
            #"unrealisedCost": 0,
            #"grossOpenCost": 0,
            #"grossOpenPremium": 0,
            #"grossExecCost": 0,
            "isOpen": True,
            #"markPrice": 0,
            #"markValue": 0,
            #"riskValue": 0,
            #"homeNotional": 0,
            #"foreignNotional": 0,
            #"posState": "string",
            #"posCost": 0,
            #"posCost2": 0,
            #"posCross": 0,
            #"posInit": 0,
            #"posComm": 0,
            #"posLoss": 0,
            #"posMargin": 0,
            #"posMaint": 0,
            #"posAllowance": 0,
            #"taxableMargin": 0,
            #"initMargin": 0,
            #"maintMargin": 0,
            #"sessionMargin": 0,
            #"targetExcessMargin": 0,
            #"varMargin": 0,
            #"realisedGrossPnl": 0,
            #"realisedTax": 0,
            #"realisedPnl": 0,
            #"unrealisedGrossPnl": 0,
            #"longBankrupt": 0,
            #"shortBankrupt": 0,
            #"taxBase": 0,
            #"indicativeTaxRate": 0,
            #"indicativeTax": 0,
            #"unrealisedTax": 0,
            "unrealisedPnl": Position.get_list_value(raw_position, PositionModel.PL, 0),
            #"unrealisedPnlPcnt": 0,
            #"unrealisedRoePcnt": 0,
            #"simpleQty": 0,
            #"simpleCost": 0,
            #"simpleValue": 0,
            #"simplePnl": 0,
            #"simplePnlPcnt": 0,
            #"avgCostPrice": 0,
            "avgEntryPrice": Position.get_list_value(raw_position, PositionModel.BASE_PRICE, 0),
            #"breakEvenPrice": 0,
            #"marginCallPrice": 0,
            "liquidationPrice": Position.get_list_value(raw_position, PositionModel.PRICE_LIQ, 0),
            #"bankruptPrice": 0,
            "timestamp": Position.get_list_value(raw_position, PositionModel.MTS_UPDATE, 0),
            #"lastPrice": 0,
            #"lastValue": 0
            "meta": Position.get_list_value(raw_position, PositionModel.META, {})
        }

    @staticmethod
    def get_position_status(position):
        status_str = position["status"]
        if status_str.startswith(PositionStatus.ACTIVE):
            return PositionStatus.ACTIVE
        if status_str.startswith(PositionStatus.CLOSED):
            return PositionStatus.CLOSED

    @staticmethod
    def get_position_trade_info(position):
        position_meta_info = position["meta"]
        if position_meta_info["reason"] == PositionTradeInfoReason.TRADE:
            return PositionTradeInfo(position_meta_info)
        else:
            return None
