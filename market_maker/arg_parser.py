import argparse


class ArgParser(object):
    @staticmethod
    def parse_args_common():
        parser = argparse.ArgumentParser(description='Parameters')

        parser.add_argument('-e', '--env',
                            type=str,
                            required=True,
                            help='Environment: live or test')

        parser.add_argument('-n', '--number_of_bots',
                            type=int,
                            required=True,
                            help='Number of bots')

        parser.add_argument('-x', '--exchange',
                            type=str,
                            required=False,
                            help='Exchange')

        parser.add_argument('-b', '--botid',
                            type=str,
                            required=False,
                            help='Bot ID')

        parser.add_argument('-i', '--instanceid',
                            type=str,
                            required=False,
                            help='Instance ID')

        parser.add_argument('--debug',
                            action='store_true',
                            help=('Print Debugs'))

        return parser.parse_args()
