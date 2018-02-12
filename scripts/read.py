import time

import cache
import vkapi
from log import datetime_format

def main(a, args):
    dialogs = a.messages.getDialogs(unread=1)['items']
    messages = {}
    users = []
    chats = []
    with a.delayed() as dm:
        for msg in dialogs:
            def cb(req, resp):
                messages[req['peer_id']] = resp['items'][::-1]

            dm.messages.getHistory.(peer_id=vkapi.utils.getSender(msg['message']), count=min(msg['unread'], 10)).set_callback(cb)
            if 'chat_id' in msg['message']:
                chats.append(msg['message']['chat_id'])
            else:
                users.append(msg['message']['user_id'])
    uc = cache.UserCache(a, 'online')
    cc = cache.ConfCache(a)
    uc.load(users)
    cc.load(chats)
    mids = []
    if dialogs:
        print('-------------------------\n')
    else:
        print('Nothing here')
    for msg in dialogs:
        m = msg['message']
        if 'chat_id' in m:
            print('Chat "{}" ({}): {}'.format(cc[m['chat_id']]['title'], m['chat_id'], msg['unread']))
        else:
            print('{} {} ({}){}: {}'.format(uc[m['user_id']]['first_name'], uc[m['user_id']]['last_name'], m['user_id'],
                  ', online' if uc[m['user_id']]['online'] else '', msg['unread']))
        print()
        for i in messages[vkapi.utils.getSender(msg['message'])]:
            if 'attachments' in i:
                for a in i['attachments']:
                    if a['type'] == 'photo':
                        i['body'] += ' (' + a['photo'].get('photo_604') + ')'
            print('[{}] {}'.format(time.strftime(datetime_format, time.localtime(i['date'])), i['body']))
            print()
            if 'chat_id' not in m:
                mids.append(i['id'])
        print('-------------------------\n')

    if 't' in args:
        print(flush=True)
        mr = vkapi.MessageReceiver(a)
        while True:
            time.sleep(1)
            for m in mr.getMessages():
                if 'chat_id' in m:
                    print('Chat "{}" ({}), {} {}:'.format(cc[m['chat_id']]['title'], m['chat_id'],
                                                          uc[m['user_id']]['first_name'], uc[m['user_id']]['last_name']))
                else:
                    print('{} {} ({}):'.format(uc[m['user_id']]['first_name'], uc[m['user_id']]['last_name'], m['user_id']))
                print('[{}] {}'.format(time.strftime(datetime_format, time.localtime(m['date'])), m['body']))
                print(flush=True)
    elif 'd' in args and mids:
        print('Deleting {} messages'.format(len(mids)))
        a.messages.delete(message_ids=','.join(map(str, mids)))
