import logging
import os
import socket
import time
import urllib.error
from urllib.request import urlopen

logger = logging.getLogger('captcha')

class CaptchaHandler:
    def __init__(self, params):
        self.png_exists = False
        self.key = params.get('antigate_key')
        self.png_filename = params.get('png_filename', 'captcha.png')
        self.txt_filename = params.get('txt_filename', 'captcha.txt')
        self.timeout = params.get('timeout', 10)
        self.checks_before_antigate = params.get('checks_before_antigate', 1)
        self.check_interval = params.get('check_interval', 5)

    def receive(self, url):
        try:
            data = urlopen(url, timeout=self.timeout).read()
        except (urllib.error.URLError, socket.timeout):
            logger.warning('captcha timeout')
            time.sleep(5)
            self.receive(url)
        except Exception:
            logger.exception('captcha.receive error')
            time.sleep(5)
            self.receive(url)
        else:
            self.png_exists = True
            with open(self.png_filename, 'wb') as f:
                f.write(data)

    def delete(self):
        if not self.png_exists:
            return
        try:
            os.remove(self.png_filename)
        except FileNotFoundError:
            pass
        self.png_exists = False

    def solve(self):
        if not os.path.isfile(self.png_filename):
            logger.warning('captcha.png does not exist')
            return ''
        import antigate
        try:
            return str(antigate.AntiGate(self.key, self.png_filename)) or None
        except antigate.AntiGateError as e:
            logger.warning(str(e))
            return None
        except Exception:
            logger.exception('captcha.solve error')
            return ''

    def handle(self, data_array, params):
        params['_trying_external_key'] = False
        if params.get('_checks_done', 0) == 0:
            logger.warning('Captcha needed')
            params['_sid'] = data_array['error']['captcha_sid']
            with open(self.txt_filename, 'w') as f:
                f.write('sid ' + params['_sid'])
            self.receive(data_array['error']['captcha_img'])
        elif params.get('_sid'):
            key = open(self.txt_filename).read()
            if key.startswith('key'):
                logger.info('Trying a key from captcha.txt')
                params['captcha_sid'] = params['_sid']
                params['captcha_key'] = key.split()[1]
                del params['_sid']
                self.delete()
                params['_checks_done'] = 0
                params['_trying_external_key'] = True
                return

        if self.key and params.get('_checks_done', 0) == self.checks_before_antigate:
            logger.info('Using antigate')
            open(self.txt_filename, 'w').close()
            ans = self.solve()
            if ans is None:
                time.sleep(5)
            elif not ans:
                self.receive(data_array['error']['captcha_img'])
                params['_sid'] = data_array['error']['captcha_sid']
            else:
                params['captcha_sid'] = params['_sid']
                params['captcha_key'] = ans
                params['_checks_done'] = 1
        else:
            time.sleep(self.check_interval)
            params['_checks_done'] = params.get('_checks_done', 0) + 1

    def reset(self, params):
        if params.get('_checks_done') or params.get('_trying_external_key'):
            if 'captcha_key' in params:
                with open(self.txt_filename, 'w') as f:
                    f.write('cor ' + params['captcha_key'])
            params['_checks_done'] = 0
            params['_trying_external_key'] = False
            params['_sid'] = ''
            logger.info('Captcha no longer needed')
            self.delete()
