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
    META string
    """

    def __init__(self, symbol, status, amount, b_price, m_funding, m_funding_type,
                 profit_loss, profit_loss_perc, l_price, lev, oid, mts_create, mts_update, type, collateral, collateral_min, meta_json):
        self.symbol = symbol
        self.status = status
        self.amount = amount
        self.base_price = b_price
        self.margin_funding = m_funding
        self.margin_funding_type = m_funding_type
        self.profit_loss = profit_loss
        self.profit_loss_percentage = profit_loss_perc
        self.liquidation_price = l_price
        self.leverage = lev
        self.id = oid
        self.mts_create = mts_create
        self.mts_update = mts_update
        self.type = type
        self.collateral = collateral
        self.collateral_min = collateral_min
        self.meta_json = meta_json

    @staticmethod
    def from_raw_position(raw_position):
        """
        Parse a raw position object into a Position object

        @return Position
        """
        symbol = raw_position[PositionModel.SYMBOL]
        status = raw_position[PositionModel.STATUS]
        amount = raw_position[PositionModel.AMOUNT]
        b_price = raw_position[PositionModel.BASE_PRICE]
        m_funding = raw_position[PositionModel.MARGIN_FUNDING]
        m_funding_type = raw_position[PositionModel.MARGIN_FUNDING_TYPE]
        profit_loss = raw_position[PositionModel.PL]
        profit_loss_perc = raw_position[PositionModel.PL_PERC]
        l_price = raw_position[PositionModel.PRICE_LIQ]
        lev = raw_position[PositionModel.LEVERAGE]
        oid = raw_position[PositionModel.ID]
        mts_create = raw_position[PositionModel.MTS_CREATE]
        mts_update = raw_position[PositionModel.MTS_UPDATE]
        otype = raw_position[PositionModel.TYPE]
        collateral = raw_position[PositionModel.COLLATERAL]
        collateral_min = raw_position[PositionModel.COLLATERAL_MIN]
        meta_json = raw_position[PositionModel.META]

        return Position(symbol, status, amount, b_price, m_funding, m_funding_type,
                        profit_loss, profit_loss_perc, l_price, lev, oid, mts_create,
                        mts_update, otype, collateral, collateral_min, meta_json)

    def __str__(self):
        ''' Allow us to print the Trade object in a pretty format '''
        text = "Position id={}, '{}' {} x {} <status='{}' pl={}>"
        return text.format(self.id, self.symbol, self.base_price, self.amount,
                           self.status, self.profit_loss)
