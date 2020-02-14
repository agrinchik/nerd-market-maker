import argparse


class ArgParser(object):
    @staticmethod
    def parse_args_bot():
        parser = argparse.ArgumentParser(description='NerdMarketMaker Bot')

        parser.add_argument('-b', '--botid',
                            type=str,
                            required=True,
                            help='Bot ID')

        parser.add_argument('-n', '--number_of_bots',
                            type=int,
                            required=True,
                            help='Number of bots')

        parser.add_argument('-e', '--env',
                            type=str,
                            required=True,
                            help='Environment: live or test')

        parser.add_argument('--debug',
                            action='store_true',
                            help=('Print Debugs'))

        return parser.parse_args()

    @staticmethod
    def parse_args_db():
        parser = argparse.ArgumentParser(description='NerdMarketMaker Database')

        parser.add_argument('-b', '--botid',
                            type=str,
                            required=False,
                            help='Bot ID')

        parser.add_argument('-n', '--number_of_bots',
                            type=int,
                            required=False,
                            help='Number of bots')

        parser.add_argument('-e', '--env',
                            type=str,
                            required=True,
                            help='Environment: live or test')

        return parser.parse_args()

    @staticmethod
    def parse_args_create_db():
        parser = argparse.ArgumentParser(description='Create NerdMarketMaker Database')

        parser.add_argument('-b', '--botid',
                            type=str,
                            required=False,
                            help='Bot ID')

        parser.add_argument('-n', '--number_of_bots',
                            type=int,
                            required=True,
                            help='Number of bots')

        parser.add_argument('-e', '--env',
                            type=str,
                            required=True,
                            help='Environment: live or test')

        return parser.parse_args()
