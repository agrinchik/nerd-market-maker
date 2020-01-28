from __future__ import absolute_import

import importlib
import os
import sys
import argparse

from market_maker.utils.bitmex.dotdict import dotdict


def import_path(fullpath):
    """
    Import a file with full path specification. Allows one to
    import from anywhere, something __import__ does not do.
    """
    path, filename = os.path.split(fullpath)
    filename, ext = os.path.splitext(filename)
    sys.path.insert(0, path)
    module = importlib.import_module(filename, path)
    importlib.reload(module)  # Might be out of date
    del sys.path[0]
    return module


def parse_args():
    parser = argparse.ArgumentParser(description='NerdMarketMaker')

    parser.add_argument('-b', '--botid',
                        type=str,
                        required=True,
                        help='Bot ID')

    parser.add_argument('-n', '--number_of_bots',
                        type=int,
                        required=True,
                        help='Number of bots')

    parser.add_argument('--live',
                        action='store_true',
                        help=('Execution Live flag'))

    parser.add_argument('--debug',
                        action='store_true',
                        help=('Print Debugs'))

    return parser.parse_args()


def resolve_settings_filename(is_live_flag):
    if is_live_flag:
        return "settings_live"
    else:
        return "settings_test"


args = parse_args()

settings_filename = resolve_settings_filename(args.live)
userSettings = import_path(os.path.join('.', settings_filename))

# Assemble settings.
settings = {}
settings.update(vars(userSettings))

settings["BOTID"] = args.botid
settings["NUMBER_OF_BOTS"] = args.number_of_bots
config_entry = settings["PORTFOLIO_BOT_CONFIG"][settings["BOTID"]]
settings["EXCHANGE"] = config_entry["exchange"]
settings["SYMBOL"] = config_entry["symbol"]

# Main export
settings = dotdict(settings)
