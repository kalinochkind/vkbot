import time

# noinspection PyUnusedLocal
def main(a, args):
    a.account.setOnline()
    while args:
        time.sleep(300)
        a.account.setOnline()
