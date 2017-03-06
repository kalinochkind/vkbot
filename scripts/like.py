# male/female - like only them
# nodup - do not like the same user twice
# nogroup - do not like group posts
# skipold - do not break if the post is already liked
# avas - like avatars too


import logging
import time

import scriptlib

def main(a, args):
    if not args:
        args = [input('Enter id: ')]
    uid = scriptlib.resolveDomain(a, args[0])
    args = args[1:]
    sex = 0
    if 'male' in args:
        sex = 2
    elif 'female' in args:
        sex = 1
    if uid is None:
        print('fail')
        return
    data = a.wall.get(owner_id=uid, count=100, extended=1, fields="sex,blacklisted,blacklisted_by_me")
    profiles = {i['id']: i for i in data['profiles']}
    liked = set()
    total = 0
    try:
        for i in data['items']:
            if i['likes'].get('user_likes'):
                logging.info(str(i['id']) + ' already liked')
                if 'skipold' in args:
                    continue
                break
            if 'nogroup' in args and i['from_id'] < 0:
                continue
            if sex and i['from_id'] in profiles and profiles[i['from_id']]['sex'] != sex:
                logging.info('Skip ' + str(i['id']))
                continue
            if 'nodup' in args and i['from_id'] in liked:
                logging.info('Duplicate ' + str(i['id']))
                continue
            liked.add(i['from_id'])
            if i['from_id'] > 0 and (profiles[i['from_id']].get('blacklisted') or profiles[i['from_id']].get('blacklisted_by_me')):
                logging.info('Blacklist ' + str(i['id']))
                continue
            logging.info('Like ' + str(i['id']))
            a.likes.add(owner_id=i['owner_id'], item_id=i['id'], type='post')
            if 'avas' in args and i['from_id'] > 0:
                ava = a.users.get(user_ids=i['from_id'], fields='photo_id')[0].get('photo_id')
                if ava:
                    owner, photo = ava.split('_')
                    time.sleep(1)
                    a.likes.add(owner_id=int(owner), item_id=int(photo), type='photo')
            total += 1
            time.sleep(3)
    finally:
        logging.info('Total: {}'.format(total))
