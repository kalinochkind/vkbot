from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('-l', '--logging', action='store_true')
parser.add_argument('-d', '--database', action='store_true')
parser.add_argument('-a', '--account')
parser.add_argument('-w', '--whitelist')
args = vars(parser.parse_args())
