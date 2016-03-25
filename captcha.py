from urllib.request import urlopen
import log
import socket
import urllib.error
import os
import time
import config
import accounts

_key = config.get('antigate.key')
png_filename = accounts.getFile('captcha.png')
_has_captcha = False

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
    global _has_captcha
    _has_captcha = True
    with open(png_filename, 'wb') as f:
        f.write(data)

def delete():
    global _has_captcha
    if not _has_captcha:
        return
    try:
        os.remove(png_filename)
    except FileNotFoundError:
        pass
    _has_captcha = False

def solve():
    if not os.path.isfile(png_filename):
        log.warning('captcha.png does not exist')
        return ''
    import antigate
    try:
        return str(antigate.AntiGate(_key, png_filename)) or None
    except antigate.AntiGateError as e:
        log.warning(str(e))
        return None
    except Exception:
        log.error('captcha.solve error', True)
        return ''

