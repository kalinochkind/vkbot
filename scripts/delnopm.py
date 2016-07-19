#!/usr/bin/python3

import log
import accounts
import time
import config

def main(a, args):
    friends = []
    log.info('Fetching friends')
    to_del = []
    for i in range(1000000):
        log.info('page ' + str(i+1))
        fr = a.friends.get(count=1000, offset=i*1000, fields='can_write_private_message')['items']
        for j in fr:
            if not j['can_write_private_message']:
                to_del.append(str(j['id']) + '\n')
                log.info('Found id{} ({} {})'.format(j['id'], j['first_name'], j['last_name']))
        if len(fr) < 1000:
            break
    with open(accounts.getFile('noadd.txt'), 'a') as res:
        res.write(''.join(to_del))
