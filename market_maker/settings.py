from __future__ import absolute_import
from market_maker.utils.bitmex.dotdict import dotdict
from market_maker.db.model import *

args = ArgParser.parse_args_common()

# Read settings from database.
settings = {}
db_common_settings = CommonSettings.get(CommonSettings.env == args.env)
app_common_settings = CommonSettings.convert_to_app_settings(db_common_settings)
settings.update(app_common_settings)

if args.botid:
    db_bot_settings = BotSettings.get(BotSettings.exchange == args.exchange, BotSettings.bot_id == args.botid)
    settings["EXCHANGE"] = db_bot_settings.exchange
    settings["BOTID"] = db_bot_settings.bot_id
    settings["INSTANCEID"] = db_bot_settings.bot_id
    settings["SYMBOL"] = db_bot_settings.symbol
    settings["APIKEY"] = db_bot_settings.apikey
    settings["SECRET"] = db_bot_settings.secret
    settings["DEFAULT_QUOTING_SIDE"] = db_bot_settings.default_quoting_side
    settings["QUOTING_SIDE_OVERRIDE"] = db_bot_settings.quoting_side_override
else:
    settings["INSTANCEID"] = args.instanceid
settings["NUMBER_OF_BOTS"] = args.number_of_bots

# Main export
settings = dotdict(settings)
