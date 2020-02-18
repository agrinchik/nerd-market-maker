from __future__ import absolute_import

import importlib
import os
import sys

from market_maker.utils.bitmex.dotdict import dotdict
from .arg_parser import ArgParser
from market_maker.db.model import *


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

# Read settings from database.
settings = {}
db_common_settings = CommonSettings.get(CommonSettings.env == args.env)
app_common_settings = CommonSettings.convert_to_settings(db_common_settings)
settings.update(app_common_settings)

if args.botid:
    db_bot_settings = BotSettings.get(BotSettings.exchange == args.exchange, BotSettings.bot_id == args.botid)
    settings["EXCHANGE"] = db_bot_settings.exchange
    settings["BOTID"] = db_bot_settings.bot_id
    settings["INSTANCEID"] = db_bot_settings.bot_id
    settings["SYMBOL"] = db_bot_settings.symbol
    settings["APIKEY"] = db_bot_settings.apikey
    settings["SECRET"] = db_bot_settings.secret
else:
    settings["INSTANCEID"] = args.instanceid
settings["NUMBER_OF_BOTS"] = args.number_of_bots

# Main export
settings = dotdict(settings)
