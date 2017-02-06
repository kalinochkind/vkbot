import html
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .utils import DelayedCall

logger = logging.getLogger('vkapi')

CALL_INTERVAL = 0.35


def retOrCall(s, *p):
    return s(*p) if callable(s) else s


class VkApi:
    api_version = '5.62'
    methods = {'account', 'ads', 'apps', 'audio', 'auth', 'board', 'database', 'docs', 'fave', 'friends', 'gifts', 'groups', 'leads', 'likes',
               'market', 'messages', 'newsfeed',
               'notes', 'notifications', 'pages', 'photos', 'places', 'polls', 'search', 'stats', 'status', 'storage', 'users', 'utils', 'video',
               'wall', 'widgets'}

    def __init__(self, username='', password='', *, ignored_errors=None, timeout=5, log_file='', captcha_handler=None, token_file=''):
        self.log_file = log_file
        self.token_file = token_file
        if self.log_file:
            logger.info('Logging enabled')
            open(self.log_file, 'w').close()
        self.username = username
        self.password = password
        self.last_call = 0
        self.delayed_list = []
        self.max_delayed = 25
        self.ignored_errors = ignored_errors or {}
        self.timeout = timeout
        self.longpoll = {'server': '', 'key': '', 'ts': 0}
        self.api_lock = threading.RLock()
        self.ch = captcha_handler
        self.token = None
        self.getToken()

    def __getattr__(self, item):
        handler = self

        class _GroupWrapper:
            def __init__(self, group):
                self.group = group

            def __getattr__(self, subitem):
                class _MethodWrapper:
                    def __init__(self, method):
                        self.method = method

                    def __call__(self, **dp):
                        response = None

                        # noinspection PyUnusedLocal
                        def cb(req, resp):
                            nonlocal response
                            response = resp

                        with handler.api_lock:
                            self.delayed(**dp).callback(cb)
                            handler.sync()
                        return response

                    def delayed(self, *, _once=False, **dp):
                        with handler.api_lock:
                            if len(handler.delayed_list) >= handler.max_delayed:
                                handler.sync(True)
                            dc = DelayedCall(self.method, dp)
                            if not _once or dc not in handler.delayed_list:
                                handler.delayed_list.append(dc)
                        return dc

                    def walk(self, callback, **dp):
                        def cb(req, resp):
                            callback(req, resp)
                            if 'next_from' in resp:
                                req['start_from'] = resp['next_from']
                                self.delayed(**req).callback(cb)

                        self.delayed(**dp).callback(cb)

                return _MethodWrapper(self.group + '.' + subitem)

        if item not in self.methods:
            raise AttributeError(item)
        return _GroupWrapper(item)

    def execute(self, code):
        return self.apiCall('execute', {"code": code}, full_response=True)

    @staticmethod
    def encodeApiCall(s):
        return "API." + s.method + '(' + str(s.params).replace('"', '\\"').replace("'", '"') + ')'

    def writeLog(self, msg):
        if self.log_file:
            with open(self.log_file, 'a') as f:
                f.write('[{}]\n'.format(time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())) + msg + '\n\n')

    def sync(self, once=False):
        while True:
            with self.api_lock:
                dl = self.delayed_list[:]
                self.delayed_list = []
            if not dl:
                return
            if len(dl) == 1:
                dc = dl[0]
                response = self.apiCall(dc.method, dc.params, dc.retry)
                dc.called(response)
                return

            query = ['return[']
            for num, i in enumerate(dl):
                query.append(self.encodeApiCall(i) + ',')
            query.append('];')
            query = ''.join(query)
            response = self.execute(query)
            errors = response.get('execute_errors', [])
            for dc, r in zip(dl, response['response']):
                if r is False:  # it's fine here
                    error = errors.pop(0)
                    if error['method'] != dc.method:
                        logger.error('Failed to match errors with methods. Response: ' + str(response))
                        return
                    if self.processError(dc.method, dc.params, {'error': error}, dc.retry):
                        dc.retry = True
                        self.delayed_list.append(dc)
                        once = False
                    else:
                        dc.called(None)
                else:
                    dc.called(r)
            if once:
                return

    def apiCall(self, method, params, retry=False, full_response=False):
        params['v'] = self.api_version
        url = 'https://api.vk.com/method/' + method + '?' + urllib.parse.urlencode(
            {i: params[i] for i in params if not i.startswith('_')}) + '&access_token=' + self.getToken()
        with self.api_lock:
            now = time.time()
            if now - self.last_call < CALL_INTERVAL:
                time.sleep(CALL_INTERVAL - now + self.last_call)
            self.last_call = now
            try:
                json_string = urllib.request.urlopen(url, timeout=self.timeout).read()
            except OSError as e:
                err = str(e)
                logger.warning(method + ' failed ({})'.format(html.escape(err.strip())))
                time.sleep(1)
                return self.apiCall(method, params, retry, full_response)
            except Exception as e:
                if retry:
                    logger.exception('({}) {}: {}'.format(method, e.__class__.__name__, str(e)))
                    return None
                else:
                    time.sleep(1)
                    logger.warning('({}) {}: {}, retrying'.format(method, e.__class__.__name__, str(e)))
                    return self.apiCall(method, params, True, full_response)

            try:
                data_array = json.loads(json_string.decode('utf-8'))
            except json.decoder.JSONDecodeError:
                logger.error('Invalid JSON')
                data_array = None
            self.writeLog('method: {}, params: {}\nresponse: {}'.format(method, json.dumps(params), json.dumps(data_array)))
            duration = time.time() - now
            if duration > self.timeout:
                logger.warning('{} timeout'.format(method))

        if data_array is None:
            logger.error('data_array is None')
            return None
        if 'response' in data_array and not full_response:
            if self.ch:
                self.ch.reset(params)
            return data_array['response']
        elif 'error' in data_array:
            code = data_array['error']['error_code']
            if code == 14:  # Captcha needed
                if self.ch:
                    self.ch.handle(data_array, params)
                else:
                    logger.warning('Captcha needed')
                    time.sleep(5)
                return self.apiCall(method, params, retry, full_response)
            elif code == 5:  # Auth error
                self.login()
                return self.apiCall(method, params, retry, full_response)
            elif code == 6:  # Too many requests per second
                logger.warning('{}: too many requests per second'.format(method))
                time.sleep(2)
                return self.apiCall(method, params, retry, full_response)
            elif code == 17:  # Validation required
                logger.warning('Validation required')
                self.validate(data_array['error']['redirect_uri'])
                time.sleep(1)
                return self.apiCall(method, params, retry, full_response)
            elif self.processError(method, params, data_array, retry):
                time.sleep(1)
                return self.apiCall(method, params, True, full_response)
            else:
                return None
        elif full_response:
            return data_array
        else:
            return self.apiCall(method, params, retry, full_response)

    def processError(self, method, params, response, retry=False):
        code = response['error']['error_code']
        if (code, method) not in self.ignored_errors and (code, '*') not in self.ignored_errors:
            logger.error('{}, params {}\ncode {}: {}'.format(method, json.dumps(params), code, response['error'].get('error_msg')))
            return False
        try:
            handler = self.ignored_errors[(code, method)]
        except KeyError:
            handler = self.ignored_errors[(code, '*')]
        if not handler:
            return False
        if retry or not handler[1]:
            logger.warning(retOrCall(handler[0], params, method))
            return False
        else:
            logger.warning(retOrCall(handler[0], params, method) + ', retrying')
            return True

    def login(self):
        logger.info('Fetching new token')
        url = ('https://oauth.vk.com/token?grant_type=password&client_id=2274003&client_secret=hHbZxrka2uZ6jB1inYsH&username=' + self.username +
               '&password=' + urllib.parse.quote(self.password))
        if not self.username or not self.password:
            logger.critical('I don\'t know your login or password, sorry')
        try:
            json_string = urllib.request.urlopen(url, timeout=self.timeout).read().decode()
        except Exception:
            logger.critical('Authorization failed')
            return
        data = json.loads(json_string)
        self.token = data['access_token']
        if self.token_file:
            with open(self.token_file, 'w') as f:
                f.write(self.token)

    def getToken(self):
        if not self.token:
            try:
                self.token = open(self.token_file).read().strip()
            except FileNotFoundError:
                self.token = ''
        return self.token

    def initLongpoll(self):
        r = self.messages.getLongPollServer()
        self.longpoll = {'server': r['server'], 'key': r['key'], 'ts': self.longpoll['ts'] or r['ts']}

    def getLongpoll(self, mode=2):
        if not self.longpoll['server']:
            self.initLongpoll()
        url = 'https://{}?act=a_check&key={}&ts={}&wait=25&mode={}&version=1'.format(
            self.longpoll['server'], self.longpoll['key'], self.longpoll['ts'], mode)
        try:
            json_string = urllib.request.urlopen(url, timeout=30).read()
        except urllib.error.HTTPError as e:
            logger.warning('longpoll http error ' + str(e.code))
            return []
        except OSError as e:
            logger.warning('longpoll failed ({})'.format(html.escape(str(e).strip())))
            time.sleep(1)
            return []
        data_array = json.loads(json_string.decode('utf-8'))
        self.writeLog('longpoll request\nresponse: {}'.format(json.dumps(data_array)))
        if 'ts' in data_array:
            self.longpoll['ts'] = data_array['ts']

        if 'updates' in data_array:
            return data_array['updates']
        elif data_array['failed'] != 1:
            self.initLongpoll()
            return []
        else:
            return self.getLongpoll(mode)

    def validate(self, url):
        if not self.username or '@' in self.username:
            logger.critical("I don't know your phone number")
        page = urllib.request.urlopen(url).read().decode()
        url_re = re.compile(r'/(login.php\?act=security_check&[^"]+)"')
        post_url = 'https://m.vk.com/' + url_re.search(page).group(1)
        phone = self.username[-10:-2]
        urllib.request.urlopen(post_url, ('code=' + phone).encode('utf-8'))
