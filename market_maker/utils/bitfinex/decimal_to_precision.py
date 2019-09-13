import decimal
import re


def number_to_string(x):
    # avoids scientific notation for too large and too small numbers
    d = decimal.Decimal(str(x))
    return '{:f}'.format(d)


def precision_from_string(string):
    parts = re.sub(r'0+$', '', string).split('.')
    return len(parts[1]) if len(parts) > 1 else 0

