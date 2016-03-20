from urllib.request import urlopen
from antigate import AntiGate, AntiGateError
import log
import socket
import urllib.error
import os
import time
import config
import accounts

_key = config.get('antigate.key')
png_filename = accounts.getFile('captcha.png')

def receive(url, timeout=10):
    try:
        data = urlopen(url, timeout=timeout).read()
    except (urllib.error.URLError, socket.timeout):
        log.warning('captcha timeout')
        time.sleep(5)
        receive(url, timeout)
    except Exception:
        log.error('captcha.receive error', True)
        time.sleep(5)
        receive(url, timeout)
    with open(png_filename, 'wb') as f:
        f.write(data)

def delete():
    try:
        os.remove(png_filename)
    except FileNotFoundError:
        pass

def solve():
    if not os.path.isfile(png_filename):
        log.warning('captcha.png does not exist')
        return ''
    try:
        return str(AntiGate(_key, png_filename)) or None
    except AntiGateError as e:
        log.warning(str(e))
        return None
    except Exception:
        log.error('captcha.solve error', True)
        return ''

