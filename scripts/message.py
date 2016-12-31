import scriptlib
import random

def main(a, args):
    if len(args) < 2:
        print('Usage: ... -s message PID MESSAGE')
        return
    pid = scriptlib.resolvePid(a, args[0])
    msg = args[1]
    a.messages.send(peer_id=pid, message=msg, random_id = random.randint(1, 10**20))
