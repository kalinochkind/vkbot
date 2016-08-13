from urllib.request import urlopen
import log
import socket
import urllib.error
import os
import time
import config
import accounts

class CaptchaHandler:

    key = config.get('captcha.antigate_key')
    png_filename = accounts.getFile('captcha.png')
    timeout = 10
    checks_before_antigate = config.get('captcha.checks_before_antigate', 'i')
    check_interval = config.get('captcha.check_interval', 'i')

    def __init__(self):
        self.has_captcha = False
        self.external = False
        self.delayed_count = 0
        self.sid = ''

    def receive(self, url):
        try:
            data = urlopen(url, timeout=self.timeout).read()
        except (urllib.error.URLError, socket.timeout):
            log.warning('captcha timeout')
            time.sleep(5)
            self.receive(url)
        except Exception:
            log.error('captcha.receive error', True)
            time.sleep(5)
            self.receive(url)
        else:
            self.has_captcha = True
            with open(self.png_filename, 'wb') as f:
                f.write(data)

    def delete(self):
        if not self.has_captcha:
            return
        try:
            os.remove(self.png_filename)
        except FileNotFoundError:
            pass
        self.has_captcha = False

    def solve(self):
        if not os.path.isfile(self.png_filename):
            log.warning('captcha.png does not exist')
            return ''
        import antigate
        try:
            return str(antigate.AntiGate(self.key, self.png_filename)) or None
        except antigate.AntiGateError as e:
            log.warning(str(e))
            return None
        except Exception:
            log.error('captcha.solve error', True)
            return ''

    def handle(self, data_array, params):
        self.external = False
        if self.delayed_count == 0:
            log.warning('Captcha needed')
            self.sid = data_array['error']['captcha_sid']
            with open(accounts.getFile('captcha.txt'), 'w') as f:
                f.write('sid ' + self.sid)
            self.receive(data_array['error']['captcha_img'])
        elif self.sid:
            key = open(accounts.getFile('captcha.txt')).read()
            if key.startswith('key'):
                log.info('Trying a key from captcha.txt')
                params['captcha_sid'] = self.sid
                params['captcha_key'] = key.split()[1]
                self.sid = ''
                self.delete()
                self.delayed_count = 0
                self.external = True
                return
        if self.delayed_count == self.checks_before_antigate:
            log.info('Using antigate')
            open(accounts.getFile('captcha.txt'), 'w').close()
            ans = self.solve()
            if ans is None:
                time.sleep(5)
            elif not ans:
                self.receive(data_array['error']['captcha_img'])
                self.sid = data_array['error']['captcha_sid']
            else:
                params['captcha_sid'] = self.sid
                params['captcha_key'] = ans
                self.delayed_count = 0
        else:
            time.sleep(self.check_interval)
            self.delayed_count += 1

    def reset(self):
        if self.delayed_count or self.external:
            self.delayed_count = 0
            self.external = False
            log.info('Captcha no longer needed')
            self.sid = ''
        self.delete()
