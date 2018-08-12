import logging

import accounts
import log
import scriptlib

from collections import defaultdict

# noinspection PyUnusedLocal
def main(a, args):
    a.timeout = 10
    friends = scriptlib.getFriends(a, fields='country')
    foll = scriptlib.getFollowers(a, fields='country')

    c = defaultdict(int)
    for u in friends + foll:
        if 'country' in u:
            c[(u['country']['title'], u['country']['id'])] += 1
        else:
            c[('-', 0)] += 1
    items = sorted(c.items(), key=lambda x: x[1], reverse=True)
    for i in items:
        print(*i)
