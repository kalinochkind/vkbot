import time

import scriptlib
import vkapi

def main(a, args):
    if not args:
        args = [input('Enter uids: ')]
    uids = ' '.join(args).replace(',', ' ').split()
    uids = [scriptlib.resolvePid(a, i) for i in uids]
    if not uids or None in uids:
        print('fail')
        return
    dm = a.delayed()
    while True:
        for i in uids:
            dm.messages.setActivity(type='typing', user_id=i)
        dm.sync()
        time.sleep(vkapi.utils.TYPING_INTERVAL)
