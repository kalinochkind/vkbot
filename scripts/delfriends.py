#!/usr/bin/python3

import log
import accounts
import time
import config

def main(a, args):
    days = config.get('delfriends.days_till_unfriend', 'i')
    prepare = 'prepare' in args
    if prepare:
        f = open(accounts.getFile('_delfriends.txt'), 'w')
    else:
        try:
            f = set(map(int, open(accounts.getFile('_delfriends.txt')).read().split()))
        except FileNotFoundError:
            log.info('_delfriends.txt not found')
            return
    friends = []
    log.info('Fetching friends')
    for i in range(1000000):
        log.info('page ' + str(i+1))
        fr = a.friends.get(count=1000, offset=i*1000)
        friends.extend(fr['items'])
        if len(fr['items']) < 1000:
            break
    now = time.time()
    to_del = []
    cnt = 0
    def checkHistory(req, resp):
        nonlocal cnt
        if resp['count'] == 0 or now - resp['items'][0]['date'] > 3600 * 24 * days:
            if prepare:
                f.write(str(req['user_id']) + '\n')
            else:
                to_del.append(str(req['user_id']) + '\n')
            log.info('Found ' + str(req['user_id']))
            cnt += 1
    for i in friends:
        if not prepare and i not in f:
            continue
        a.messages.getHistory.delayed(count=1, user_id=i).callback(checkHistory)
    a.sync()
    if prepare:
        f.close()
    else:
        with open(accounts.getFile('noadd.txt'), 'a') as res:
            res.write(''.join(to_del))
    log.info('Total: ' + str(cnt))
