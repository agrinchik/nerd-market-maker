from __future__ import absolute_import

import importlib
import os
import sys

from market_maker.utils.bitmex.dotdict import dotdict
from .arg_parser import ArgParser


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


def resolve_settings_filename(env):
    if env == "live":
        return "settings_live"
    elif env == "test":
        return "settings_test"


args = ArgParser.parse_args_common()

settings_filename = resolve_settings_filename(args.env)
userSettings = import_path(os.path.join('.', settings_filename))

# Assemble settings.
settings = {}
settings.update(vars(userSettings))

if args.botid:
    settings["BOTID"] = args.botid
    settings["INSTANCEID"] = args.botid
    config_entry = settings["PORTFOLIO_BOT_CONFIG"][args.botid]
    settings["EXCHANGE"] = config_entry["exchange"]
    settings["SYMBOL"] = config_entry["symbol"]
else:
    settings["INSTANCEID"] = args.instanceid
settings["NUMBER_OF_BOTS"] = args.number_of_bots

# Main export
settings = dotdict(settings)
