from urllib.request import urlopen
from antigate import AntiGate, AntiGateError
import log
import socket
import urllib.error
import os

_key = open('antigate.txt').read().strip()

def receive(url, timeout=10):
    try:
        data = urlopen(url, timeout=timeout).read()
    except (urllib.error.URLError, socket.timeout):
        log.warning('captcha timeout')
        return None
    except Exception:
        log.error('captcha error', True)
        return None
    with open('captcha.png', 'wb') as f:
        f.write(data)

def delete():
    try:
        os.remove('captcha.png')
    except FileNotFoundError:
        pass

def solve():
    try:
        return str(AntiGate(_key, 'captcha.png')) or None
    except AntiGateError as e:
        log.warning(str(e))
        return None
    except Exception:
        log.error('captcha error', True)
        return None
    finally:
        delete()
