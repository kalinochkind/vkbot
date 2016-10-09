from urllib.request import urlopen
import logging
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
        self.png_exists = False

    def receive(self, url):
        try:
            data = urlopen(url, timeout=self.timeout).read()
        except (urllib.error.URLError, socket.timeout):
            logging.warning('captcha timeout')
            time.sleep(5)
            self.receive(url)
        except Exception:
            logging.exception('captcha.receive error')
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
            logging.warning('captcha.png does not exist')
            return ''
        import antigate
        try:
            return str(antigate.AntiGate(self.key, self.png_filename)) or None
        except antigate.AntiGateError as e:
            logging.warning(str(e))
            return None
        except Exception:
            logging.exception('captcha.solve error')
            return ''

    def handle(self, data_array, params):
        params['_trying_external_key'] = False
        if params.get('_checks_done', 0) == 0:
            logging.warning('Captcha needed')
            params['_sid'] = data_array['error']['captcha_sid']
            with open(accounts.getFile('captcha.txt'), 'w') as f:
                f.write('sid ' + params['_sid'])
            self.receive(data_array['error']['captcha_img'])
        elif params.get('_sid'):
            key = open(accounts.getFile('captcha.txt')).read()
            if key.startswith('key'):
                logging.info('Trying a key from captcha.txt')
                params['captcha_sid'] = params['_sid']
                params['captcha_key'] = key.split()[1]
                del params['_sid']
                self.delete()
                params['_checks_done'] = 0
                params['_trying_external_key'] = True
                return

        if self.key and params.get('_checks_done') == self.checks_before_antigate:
            logging.info('Using antigate')
            open(accounts.getFile('captcha.txt'), 'w').close()
            ans = self.solve()
            if ans is None:
                time.sleep(5)
            elif not ans:
                self.receive(data_array['error']['captcha_img'])
                params['_sid'] = data_array['error']['captcha_sid']
            else:
                params['captcha_sid'] = params['_sid']
                params['captcha_key'] = ans
                params['_checks_done'] = 0
        else:
            time.sleep(self.check_interval)
            params['_checks_done'] = params.get('_checks_done', 0) + 1

    def reset(self, params):
        if params.get('_checks_done') or params.get('_trying_external_key'):
            params['_checks_done'] = 0
            params['_trying_external_key'] = False
            params['_sid'] = ''
            logging.info('Captcha no longer needed')
            self.delete()
