
class RobotInfo(object):

    def __init__(self):
        pass

    @staticmethod
    def parse_from_number(robot_index_num):
        if robot_index_num < 0 or robot_index_num > 999:
            raise Exception("Invalid robot index number: {}".format(robot_index_num))
        return "Robot{:03d}".format(robot_index_num)

    @staticmethod
    def parse_for_tg_logs(robot_id_str):
        if not robot_id_str or len(robot_id_str) != 8:
            raise Exception("Invalid Robot Id: {}".format(robot_id_str))
        robot_id_str_u = robot_id_str.upper()
        return "{}_{}".format(robot_id_str_u[0:5], robot_id_str_u[5:8])

