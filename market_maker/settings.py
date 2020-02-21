from __future__ import absolute_import
from market_maker.utils.bitmex.dotdict import dotdict
from market_maker.db.model import *

args = ArgParser.parse_args_common()

# Read settings from database.
settings = {}
db_common_settings = CommonSettings.get(CommonSettings.env == args.env)
app_common_settings = CommonSettings.convert_to_app_settings(db_common_settings)
settings.update(app_common_settings)

if args.robotid:
    db_robot_settings = RobotSettings.get(RobotSettings.exchange == args.exchange, RobotSettings.robot_id == args.robotid)
    settings["EXCHANGE"] = db_robot_settings.exchange
    settings["ROBOTID"] = db_robot_settings.robot_id
    settings["INSTANCEID"] = db_robot_settings.robot_id
    settings["SYMBOL"] = db_robot_settings.symbol
    settings["APIKEY"] = db_robot_settings.apikey
    settings["SECRET"] = db_robot_settings.secret
    settings["QUOTING_SIDE_OVERRIDE"] = db_robot_settings.quoting_side_override
else:
    settings["INSTANCEID"] = args.instanceid
settings["NUMBER_OF_ROBOTS"] = args.number_of_robots

# Main export
settings = dotdict(settings)
