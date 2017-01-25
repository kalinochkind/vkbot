import time

import scriptlib
import vkapi

def main(a, args):
    if not args:
        args = [input('Enter uid: ')]
    uid = scriptlib.resolvePid(a, args[0])
    if uid is None:
        print('fail')
        return
    while True:
        a.messages.setActivity(type='typing', user_id=uid)
        time.sleep(vkapi.utils.TYPING_INTERVAL)
