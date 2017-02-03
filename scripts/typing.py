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
    while True:
        for i in uids:
            a.messages.setActivity.delayed(type='typing', user_id=i)
        a.sync()
        time.sleep(vkapi.utils.TYPING_INTERVAL)
