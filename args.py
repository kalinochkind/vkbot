from argparse import ArgumentParser, REMAINDER

parser = ArgumentParser()
parser.add_argument('-l', '--logging', action='store_true')
parser.add_argument('-d', '--database', action='store_true')
parser.add_argument('-a', '--account')
parser.add_argument('-w', '--whitelist')
parser.add_argument('-s', '--script', default='', nargs='?')
parser.add_argument('args', nargs=REMAINDER)
args = vars(parser.parse_args())
