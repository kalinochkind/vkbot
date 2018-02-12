import logging

import scriptlib

def attachments(a, items):
    for i in items:
        if i['attachment']['photo']['owner_id'] == self_id:
            if i['attachment']['photo']['id'] in good:
                continue
            a.photos.delete(photo_id=i['attachment']['photo']['id'])
            logging.info('Found ' + str(i['attachment']['photo']['id']))

self_id = 0
good = []

# noinspection PyUnusedLocal
def main(a, args):
    a.timeout = 10
    dialogs = scriptlib.getDialogs(a)
    logging.info(str(len(dialogs)) + ' dialogs found')
    global self_id, good
    self_id = a.users.get()[0]['id']
    good = [i['id'] for i in a.photos.get(count=1000, album_id='profile')['items']]
    good += [i['id'] for i in a.photos.get(count=1000, album_id='wall')['items']]
    with a.delayed() as dm:
        for num, i in enumerate(dialogs):
            logging.info('{} ({}/{})'.format(i, num + 1, len(dialogs)))
            dm.messages.getHistoryAttachments(peer_id=i, media_type='photo', count=200).walk(lambda req, res: attachments(dm, res['items']))
