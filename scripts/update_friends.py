import logging

import accounts
import check_friend
import log
import scriptlib

# noinspection PyUnusedLocal
def main(a, args):
    a.timeout = 10
    banned = list(map(int, open(accounts.getFile('banned.txt')).read().split()))
    friends = scriptlib.getFriends(a, fields=check_friend.fields)

    logging.info('Starting to delete')
    for i in friends:
        if not (check_friend.isGood(i) or i['id'] in banned):
            a.friends.delete.delayed(user_id=i['id'])
            logging.info('deleted ' + str(i['id']))
            log.write('_update_friends', 'deleted ' + str(i['id']))

    foll = scriptlib.getFollowers(a, fields=check_friend.fields)

    logging.info('Starting to add')
    for i in foll:
        if check_friend.isGood(i):
            a.friends.add.delayed(user_id=i['id'])
            logging.info('added ' + str(i['id']))
            log.write('_update_friends', 'added ' + str(i['id']))
    logging.info('\nFinished')
