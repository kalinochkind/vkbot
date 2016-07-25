import threading
import urllib.request
import json
import time
import socket
import config
import log
import captcha
import accounts
import args
from http.client import RemoteDisconnected

CALL_INTERVAL = 0.35

class DelayedCall:

    def __init__(self, method, params):
        self.method = method
        self.params = params
        self.callback_func = None

    def callback(self, func, *p):
        self.callback_func = func
        return self

    def _called(self, response):
        if self.callback_func:
            self.callback_func(self.params, response)


class vk_api:
    checks_before_antigate = config.get('vkapi.checks_before_antigate', 'i')
    captcha_check_interval = config.get('vkapi.captcha_check_interval', 'i')
    api_version = '5.52'

    def __init__(self, username='', password='', *, ignored_errors={}, timeout=config.get('vkapi.default_timeout', 'i')):
        self.logging = bool(args.args['logging'])
        if self.logging:
            log.info('Logging enabled')
        self.username = username
        self.password = password
        self.captcha_delayed = 0
        self.captcha_sid = ''
        self.last_call = 0
        self.delayed_list = []
        self.max_delayed = 25
        self.ignored_errors = ignored_errors
        self.timeout = timeout
        self.longpoll_server = ''
        self.longpoll_key = ''
        self.longpoll_ts = 0
        self.api_lock = threading.RLock()
        self.token = None
        self.getToken()
        self.externalCaptcha = False
        self.captchaError = False

    def __getattr__(self, item):
        handler = self
        class _group_wrapper:
            def __init__(self, group):
                self.group = group
            def __getattr__(self, item):
                class _method_wrapper:
                    def __init__(self, method):
                        self.method = method
                    def __call__(self, **dp):
                        response = None
                        def cb(req, resp):
                            nonlocal response
                            response = resp
                        self.delayed(**dp).callback(cb)
                        handler.sync()
                        return response
                    def delayed(self, **dp):
                        with handler.api_lock:
                            if len(handler.delayed_list) >= handler.max_delayed:
                                handler.sync()
                            dc = DelayedCall(self.method, dp)
                            handler.delayed_list.append(dc)
                        return dc
                return _method_wrapper(self.group + '.' + item)
        if item not in ['users', 'auth', 'wall', 'photos', 'friends', 'widgets', 'storage', 'status', 'audio', 'pages',
                    'groups', 'board', 'video', 'notes', 'places', 'account', 'messages', 'newsfeed', 'likes', 'polls',
                    'docs', 'fave', 'notifications', 'stats', 'search', 'apps', 'utils', 'database', 'gifts', 'market']:
            raise AttributeError(item)
        return _group_wrapper(item)

    def execute(self, code):
        return self.apiCall('execute', {"code": code})

    @staticmethod
    def encodeApiCall(s):
        return "API." + s.method + '(' + str(s.params).replace('"', '\\"').replace("'", '"') + ')'

    def sync(self):
        with self.api_lock:
            if not self.delayed_list:
                return
            dl = self.delayed_list
            self.delayed_list = []
            if len(dl) == 1:
                dc = dl[0]
                response = self.apiCall(dc.method, dc.params)
                dc._called(response)
                return

            query = ['return[']
            for num, i in enumerate(dl):
                query.append(self.encodeApiCall(i) + ',')
            query.append('];')
            query = ''.join(query)
            response = self.execute(query)
            for dc, r in zip(dl, response):
                dc._called(r)

    def apiCall(self, method, params, retry=False):
        with self.api_lock:
            params['v'] = self.api_version
            url = 'https://api.vk.com/method/' + method + '?' + urllib.parse.urlencode(params) + '&access_token=' + self.getToken()
            now = time.time()
            if now - self.last_call < CALL_INTERVAL:
                time.sleep(CALL_INTERVAL - now + self.last_call)
            self.last_call = now
            try:
                json_string = urllib.request.urlopen(url, timeout=self.timeout).read()
            except OSError as e:
                err = str(e)
                if err.startswith('<urlopen error'):
                    if ':' in err:
                        err = err.split(':')[-1].rstrip('>')
                    else:
                        err = err.split(']')[-1].lstrip().rstrip('>')
                log.warning(method + ' failed ({})'.format(err.strip()))
                time.sleep(1)
                return self.apiCall(method, params)
            except Exception as e:
                if retry:
                    log.error('({}) {}: {}'.format(method, e.__class__.__name__, str(e)), True)
                    return None
                else:
                    time.sleep(1)
                    log.warning('({}) {}: {}, retrying'.format(method, e.__class__.__name__, str(e)))
                    return self.apiCall(method, params, 1)

            try:
                data_array = json.loads(json_string.decode('utf-8'))
            except json.decoder.JSONDecodeError:
                log.error('Invalid JSON')
                data_array = None
            if self.logging:
                with open('inf.log', 'a') as f:
                    print('[{}]\nmethod: {}, params: {}\nresponse: {}\n'.format(time.strftime(log.datetime_format, time.localtime()), method, json.dumps(params), json.dumps(data_array)), file=f)
            duration = time.time() - now
            if duration > self.timeout:
                log.warning('{} timeout'.format(method))

            if data_array is None:
                return None
            if 'response' in data_array:
                if self.captcha_delayed or self.externalCaptcha:
                    self.captcha_delayed = 0
                    self.externalCaptcha = False
                    log.info('Captcha no longer needed')
                    self.captcha_sid = ''
                captcha.delete()
                return data_array['response']

            elif 'error' in data_array:
                if data_array['error']['error_code'] == 14: #Captcha needed
                    self.externalCaptcha = False
                    if self.captcha_delayed == 0:
                        log.warning('Captcha needed')
                        self.captcha_sid = data_array['error']['captcha_sid']
                        with open(accounts.getFile('captcha.txt'), 'w') as f:
                            f.write('sid ' + self.captcha_sid)
                        captcha.receive(data_array['error']['captcha_img'])
                    elif self.captcha_sid:
                        key = open(accounts.getFile('captcha.txt')).read()
                        if key.startswith('key'):
                            log.info('Trying a key from captcha.txt')
                            params['captcha_sid'] = self.captcha_sid
                            params['captcha_key'] = key.split()[1]
                            self.captcha_sid = ''
                            captcha.delete()
                            self.captcha_delayed = 0
                            self.externalCaptcha = True
                            return self.apiCall(method, params)
                    if self.captcha_delayed == self.checks_before_antigate:
                        log.info('Using antigate')
                        open(accounts.getFile('captcha.txt'), 'w').close()
                        ans = captcha.solve()
                        if ans is None:
                            self.captchaError = True
                            time.sleep(5)
                        elif not ans:
                            captcha.receive(data_array['error']['captcha_img'])
                            self.captcha_sid = data_array['error']['captcha_sid']
                            return self.apiCall(method, params)
                        else:
                            params['captcha_sid'] = self.captcha_sid
                            params['captcha_key'] = ans
                            self.captcha_delayed = 0
                    else:
                        time.sleep(self.captcha_check_interval)
                        self.captcha_delayed += 1
                    return self.apiCall(method, params)
                elif data_array['error']['error_code'] == 5: #Auth error
                    self.login()
                    return self.apiCall(method, params)

                elif (data_array['error']['error_code'], method) in self.ignored_errors or (data_array['error']['error_code'], '*') in self.ignored_errors:
                    handler = self.ignored_errors[(data_array['error']['error_code'], method)]
                    if not handler:
                        return None
                    if retry or not handler[1]:
                        log.warning(handler[0])
                        return None
                    else:
                        log.warning(handler[0] + ', retrying')
                        time.sleep(3)
                        return self.apiCall(method, params, True)

                else:
                    log.error('{}, params {}\ncode {}: {}'.format(method, json.dumps(params), data_array['error']['error_code'], data_array['error'].get('error_msg')))
                    return None
            else:
                return self.apiCall(method, params)

    def login(self):
        log.info('Fetching new token')
        url = 'https://oauth.vk.com/token?grant_type=password&client_id=2274003&client_secret=hHbZxrka2uZ6jB1inYsH&username=' + self.username + '&password=' + self.password
        if not self.username or not self.password:
            log.error('I don\'t know your login or password, sorry', fatal=True)
        try:
            json_string = urllib.request.urlopen(url, timeout=self.timeout).read().decode()
        except Exception:
            log.error('Authorization failed', fatal=True)
        data = json.loads(json_string)
        self.token = data['access_token']
        with open(accounts.getFile('token.txt'), 'w') as f:
            f.write(self.token)

    def getToken(self):
        if not self.token:
            try:
                self.token = open(accounts.getFile('token.txt')).read().strip()
            except FileNotFoundError:
                self.token = ''
        return self.token

    def initLongpoll(self):
        r = self.messages.getLongPollServer()
        self.longpoll_server = r['server']
        self.longpoll_key = r['key']
        self.longpoll_ts = self.longpoll_ts or r['ts']

    def getLongpoll(self, mode=2):
        if not self.longpoll_server:
            self.initLongpoll()
        url = 'https://{}?act=a_check&key={}&ts={}&wait=25&mode={}'.format(self.longpoll_server, self.longpoll_key, self.longpoll_ts, mode)
        try:
            json_string = urllib.request.urlopen(url, timeout=30).read()
        except urllib.error.HTTPError as e:
            log.warning('longpoll http error ' + str(e.code))
            return []
        except OSError as e:
            log.warning('longpoll failed ({})'.format(e))
            time.sleep(1)
            return []
        data_array = json.loads(json_string.decode('utf-8'))
        if self.logging:
            with open('inf.log', 'a') as f:
                print('[{}]\nlongpoll request: {}\nresponse: {}\n'.format(time.strftime(log.datetime_format, time.localtime()), url, json.dumps(data_array)), file=f)
        if 'ts' in data_array:
            self.longpoll_ts = data_array['ts']

        if 'updates' in data_array:
            return data_array['updates']
        elif data_array['failed'] != 1:
            self.initLongpoll()
            return []
        else:
            return self.getLongpoll(mode)
