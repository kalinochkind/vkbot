import logging
import time

import scriptlib

def main(a, args):
    if not args:
        args = [input('Enter id: ')]
    uid = scriptlib.resolveDomain(a, args[0])
    sex = 0
    if len(args) == 2:
        if args[-1] == 'male':
            sex = 2
        elif args[-1] == 'female':
            sex = 1
    if uid is None:
        print('fail')
        return
    data = a.wall.get(owner_id=uid, count=100, extended=1, fields="sex,blacklisted,blacklisted_by_me")
    profiles = {i['id']: i for i in data['profiles']}
    liked = set()
    for i in data['items']:
        if i['likes'].get('user_likes'):
            logging.info(str(i['id']) + ' already liked, breaking')
            break
        if i['from_id'] < 0:
            continue
        if sex and i['from_id'] in profiles and profiles[i['from_id']]['sex'] != sex:
            logging.info('Skip ' + str(i['id']))
            continue
        if i['from_id'] in liked:
            logging.info('Duplicate ' + str(i['id']))
            continue
        liked.add(i['from_id'])
        if profiles[i['from_id']]['blacklisted'] or profiles[i['from_id']]['blacklisted_by_me']:
            logging.info('Blacklist ' + str(i['id']))
            continue
        logging.info('Like ' + str(i['id']))
        a.likes.add(owner_id=i['owner_id'], item_id=i['id'], type='post')
        time.sleep(3)
    logging.info('Total: {}'.format(len(liked)))
