import log
import scriptlib

def enumPhotos(peer):
    st = ''
    while 1:
        ph = a.messages.getHistoryAttachments(peer_id=peer, media_type='photo', count=200, start_from=st)
        st = ph.get('next_from')
        for i in ph['items']:
            if i['photo']['owner_id'] == self_id:
                yield (i['photo']['photo_75'], i['photo']['id'])
        if not st:
            return

def attachments(a, items, next_from, peer_id):
    for i in items:
        if i['photo']['owner_id'] == self_id:
            if i['photo']['id'] in good:
                continue
            a.photos.delete.delayed(photo_id=i['photo']['id'])
            log.info('Found ' + str(i['photo']['id']))
    if next_from:
        a.messages.getHistoryAttachments.delayed(peer_id=peer_id, media_type='photo', count=200, start_from=next_from).callback(lambda req, res: attachments(a, res['items'], res.get('next_from'), req['peer_id']))  # TODO decorator

def main(a, args):
    a.timeout = 10
    dialogs = scriptlib.getDialogs(a)
    log.info(str(len(dialogs)) + ' dialogs found')
    global self_id, good
    self_id = a.users.get()[0]['id']
    good = [i['id'] for i in a.photos.get(count=1000,album_id='profile')['items']]
    good += [i['id'] for i in a.photos.get(count=1000,album_id='wall')['items']]
    for num, i in enumerate(dialogs):
        log.info('{} ({}/{})'.format(i, num+1, len(dialogs)))
        a.messages.getHistoryAttachments.delayed(peer_id=i, media_type='photo', count=200).callback(lambda req, res: attachments(a, res['items'], res.get('next_from'), req['peer_id']))
