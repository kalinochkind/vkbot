#!/usr/bin/python3

import log
import accounts
import time
import config
import scriptlib
import check_friend

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
    friends = scriptlib.getFriends(a)
    now = time.time()
    to_del = []
    cnt = 0
    def checkHistory(req, resp):
        nonlocal cnt
        if resp['count'] == 0 or now - resp['items'][0]['date'] > 3600 * 24 * days:
            if prepare:
                f.write(str(req['user_id']) + '\n')
            else:
                to_del.append(str(req['user_id']))
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
        check_friend.appendNoadd(to_del)
    log.info('Total: ' + str(cnt))
