from datetime import datetime


def UTC_to_CurrTZ(dt):
    return datetime.fromtimestamp(dt.timestamp())

