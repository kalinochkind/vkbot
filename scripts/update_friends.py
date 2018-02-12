import logging

import accounts
import log
import scriptlib

# noinspection PyUnusedLocal
def main(a, args):
    a.ignored_errors = {
        (177, 'friends.add'): None,
    }
    a.timeout = 10
    banned = list(map(int, open(accounts.getFile('banned.txt')).read().split()))
    controller = scriptlib.createFriendController()
    friends = scriptlib.getFriends(a, fields=controller.fields)

    logging.info('Starting to delete')
    with a.delayed() as dm:
        for i in friends:
            if not (controller.isGood(i) or i['id'] in banned):
                dm.friends.delete(user_id=i['id'])
                logging.info('deleted ' + str(i['id']))
                log.write('_update_friends', 'deleted ' + str(i['id']))

    foll = scriptlib.getFollowers(a, fields=controller.fields)
    logging.info('Starting to add')
    def cb(req, resp):
        logging.info(('added ' if resp else 'error ') + str(req['user_id']))
    with a.delayed() as dm:
        for i in foll:
            if controller.isGood(i):
                dm.friends.add(user_id=i['id']).set_callback(cb)
    logging.info('\nFinished')
