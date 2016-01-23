from urllib.request import urlopen
from antigate import AntiGate, AntiGateError
import log

_key = open('antigate.txt').read().strip()
_a = None

def solve(url, timeout=10):
    try:
        data = urlopen(url, timeout=timeout).read()
    except Exception:
        log.error('captcha timeout', True)
        return None
    with open('captcha.png', 'wb') as f:
        f.write(data)
    global _a
    try:
        _a = AntiGate(_key, 'captcha.png')
    except AntiGateError as e:
        print(e)
        return None
    return str(_a)
