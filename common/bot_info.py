
class BotInfo(object):

    def __init__(self):
        pass

    @staticmethod
    def parse_from_number(bot_number):
        if bot_number < 0 or bot_number > 999:
            raise Exception("Invalid bot number: {}".format(bot_number))
        return "Bot{:03d}".format(bot_number)

    @staticmethod
    def parse_for_tg_logs(bot_id_str):
        if not bot_id_str or len(bot_id_str) != 6:
            raise Exception("Invalid Bot Id: {}".format(bot_id_str))
        bot_id_str_u = bot_id_str.upper()
        return "{}_{}".format(bot_id_str_u[0:3], bot_id_str_u[3:6])

