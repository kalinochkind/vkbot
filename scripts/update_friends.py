import logging

import accounts
import log
import scriptlib


def handleAddError(api, params, method):
    api.friends.delete(user_id=params['user_id'])
    return 'Failed to add {}, deleted'.format(params['user_id'])


# noinspection PyUnusedLocal
def main(a, args):
    a.ignored_errors = {
        (177, 'friends.add'): None,
        (1, 'friends.add'): (lambda p, m: handleAddError(a, p, m), False),
    }
    a.timeout = 10
    banned = list(map(int, open(accounts.getFile('banned.txt')).read().split()))
    controller = scriptlib.createFriendController()
    friends = scriptlib.getFriends(a, fields=controller.fields)
    friend_count = len(friends)

    dry = 'dry' in args

    logging.info('Starting to delete')
    with a.delayed() as dm:
        for i in friends:
            if not (controller.isGood(i) or i['id'] in banned):
                if not dry:
                    dm.friends.delete(user_id=i['id'])
                    log.write('_update_friends', 'deleted ' + str(i['id']))
                    logging.info('deleted ' + str(i['id']))
                else:
                    friend_count -= 1
    foll = scriptlib.getFollowers(a, fields=controller.fields)
    logging.info('Starting to add')
    def cb(req, resp):
        logging.info(('added ' if resp else 'error ') + str(req['user_id']))
    with a.delayed() as dm:
        for i in foll:
            if controller.isGood(i):
                if not dry:
                    dm.friends.add(user_id=i['id']).set_callback(cb)
                else:
                    friend_count += 1
    if dry:
        print('Friends:', friend_count)
    logging.info('\nFinished')
