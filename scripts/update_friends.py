import logging

import accounts
import log
import scriptlib

# noinspection PyUnusedLocal
def main(a, args):
    a.timeout = 10
    banned = list(map(int, open(accounts.getFile('banned.txt')).read().split()))
    controller = scriptlib.createFriendController()
    friends = scriptlib.getFriends(a, fields=controller.fields)

    logging.info('Starting to delete')
    for i in friends:
        if not (controller.isGood(i) or i['id'] in banned):
            a.friends.delete.delayed(user_id=i['id'])
            logging.info('deleted ' + str(i['id']))
            log.write('_update_friends', 'deleted ' + str(i['id']))

    foll = scriptlib.getFollowers(a, fields=controller.fields)

    logging.info('Starting to add')
    for i in foll:
        if controller.isGood(i):
            a.friends.add.delayed(user_id=i['id'])
            logging.info('added ' + str(i['id']))
            log.write('_update_friends', 'added ' + str(i['id']))
    logging.info('\nFinished')
