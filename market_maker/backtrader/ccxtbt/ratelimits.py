from market_maker.utils import log

logger = log.setup_supervisor_custom_logger('root')


class RateLimitConfig(object):

    _DEFAULT_RATE_LIMIT = 4000

    _CONFIG = {
        "bitfinex": {
            "fetch_ticker": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "get_wallet_balance": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "get_balance": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "getposition": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "create_order": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "cancel_order": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_trades": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_my_trades": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_ohlcv": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_order": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_open_orders": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
        },
        "bitmex": {
            "fetch_ticker": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "get_wallet_balance": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "get_balance": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "getposition": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "create_order": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "cancel_order": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_trades": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_my_trades": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_ohlcv": {
                "base_limit_rate": 2000,
                "apply_factor": False
            },
            "fetch_order": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
            "fetch_open_orders": {
                "base_limit_rate": 4000,
                "apply_factor": False
            },
        }
    }

    @classmethod
    def get_rate_limit(cls, exchange, method_name, factor):
        result = 0
        try:
            exchange = exchange.lower()
            config = cls._CONFIG.get(exchange).get(method_name)
            base_rate_limit = config.get("base_limit_rate")
            result = base_rate_limit
            if config.get("apply_factor") is True:
                result *= factor
            logger.debug("Calculated rate_limit for {} method: {}".format(method_name, result))
        except Exception:
            logger.error("Exception occurred. Reverted to default rate_limit for {} method: {}".format(method_name, result))
            result = cls._DEFAULT_RATE_LIMIT
        return result
