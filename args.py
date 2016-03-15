from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('-l', '--logging', action='store_true')
parser.add_argument('-d', '--database', action='store_true')
parser.add_argument('-u', '--user')
args = vars(parser.parse_args())
