import html
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .utils import *
from .upload import uploadFile
from . import auth

CALL_INTERVAL = 0.35
MAX_CALLS_IN_EXECUTE = 25


def retOrCall(s, *p):
    return s(*p) if callable(s) else s

def jsonToUTF8(d):
    if isinstance(d, str):
        try:
            return d.encode('latin1').decode('utf-8')
        except UnicodeDecodeError:
            return d.encode('latin1').decode('cp1251')
    elif isinstance(d, list):
        return [jsonToUTF8(i) for i in d]
    elif isinstance(d, dict):
        return {jsonToUTF8(i): jsonToUTF8(d[i]) for i in d}
    else:
        return d


class VkApi(VkMethodDispatcher):
    api_version = '5.95'
    longpoll_version = 3

    def __init__(self, *, ignored_errors=None, timeout=5, log_file='', captcha_handler=None, token_file=''):
        self.log_file = log_file
        self.token_file = token_file
        if self.log_file:
            logger.info('Logging enabled')
            open(self.log_file, 'w').close()
        self.limiter = RateLimiter(CALL_INTERVAL)
        self.ignored_errors = ignored_errors or {}
        self.timeout = timeout
        self.longpoll = {'server': '', 'key': '', 'ts': 0}
        self.ch = captcha_handler
        self.token = None
        self.login_params = None
        self.getToken()


    def _callMethod(self, method, kwargs):
        return self.apiCall(method, kwargs)

    def execute(self, code):
        return self.apiCall('execute', {"code": code}, full_response=True)

    @staticmethod
    def encodeApiCall(method, params):
        return "API." + method + '(' + json.dumps({i:params[i] for i in params if not i.startswith(')')}, ensure_ascii=False) + ')'

    def writeLog(self, msg):
        if self.log_file:
            with open(self.log_file, 'a') as f:
                f.write('[{}]\n'.format(time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())) + msg + '\n\n')

    def apiCall(self, method, params, full_response=False):
        params['v'] = self.api_version
        encoded = urllib.parse.urlencode({i: params[i] for i in params if not i.startswith('_')})
        post_params = None
        if len(encoded) > 1024:
            url = 'https://api.vk.com/method/' + method + '?access_token=' + (params.get('_token') or self.getToken())
            post_params = encoded.encode()
        else:
            url = 'https://api.vk.com/method/' + method + '?' + encoded + '&access_token=' + (params.get('_token') or self.getToken())
        with self.limiter:
            now = time.time()
            try:
                json_string = urllib.request.urlopen(url, data=post_params, timeout=self.timeout).read()
            except OSError as e:
                err = str(e)
                logger.warning(method + ' failed ({})'.format(html.escape(err.strip())))
                time.sleep(1)
                return self.apiCall(method, params, full_response)
            except Exception as e:
                if params.get('_retry'):
                    logger.exception('({}) {}: {}'.format(method, e.__class__.__name__, str(e)))
                    return None
                else:
                    time.sleep(1)
                    logger.warning('({}) {}: {}, retrying'.format(method, e.__class__.__name__, str(e)))
                    params['_retry'] = True
                    return self.apiCall(method, params, full_response)

            try:
                try:
                    data_array = json.loads(json_string.decode('utf-8'))
                except UnicodeDecodeError:
                    logger.warning('Invalid JSON received, trying to parse anyway')
                    data_array = jsonToUTF8(json.loads(json_string.decode('latin1')))
            except json.decoder.JSONDecodeError:
                logger.error('Invalid JSON')
                data_array = None
            self.writeLog('method: {}, params: {}\nresponse: {}'.format(method + (' (POST)' if post_params else ''), json.dumps(params), json.dumps(data_array)))
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
                return self.apiCall(method, params, full_response)
            elif code == 5:  # Auth error
                if data_array['error']['error_msg'] == 'User authorization failed: method is unavailable with group auth.':
                    raise VkError('User token required')
                self.login()
                return self.apiCall(method, params, full_response)
            elif code == 6:  # Too many requests per second
                logger.warning('{}: too many requests per second'.format(method))
                time.sleep(2)
                return self.apiCall(method, params, full_response)
            elif code == 17:  # Validation required
                logger.warning('Validation required')
                self.validate(data_array['error']['redirect_uri'])
                time.sleep(1)
                return self.apiCall(method, params, full_response)
            elif self.processError(method, params, data_array):
                time.sleep(1)
                params['_retry'] = True
                return self.apiCall(method, params, full_response)
            else:
                return None
        elif full_response:
            return data_array
        else:
            return self.apiCall(method, params, full_response)

    def processError(self, method, params, response):
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
        if params.get('_retry') or not handler[1]:
            logger.warning(retOrCall(handler[0], params, method))
            return False
        else:
            logger.warning(retOrCall(handler[0], params, method) + ', retrying')
            return True

    def login(self):
        if not self.login_params:
            logger.critical('Unable to log in, no login_params provided')
            raise VkError('login_params required')
        logger.info('Fetching new token')
        self.token = auth.login(self.login_params['username'], self.login_params['password'], self.login_params['client_id'], self.login_params['perms'])
        if not self.token:
            logger.critical('Login failed')
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
        r = self.messages.getLongPollServer(lp_version=self.longpoll_version)
        if not r:
            logger.warning('Unable to initialize longpoll')
            self.longpoll = {}
            return
        self.longpoll = {'server': r['server'], 'key': r['key'], 'ts': self.longpoll.get('ts') or r['ts']}

    def getLongpoll(self, mode=2):
        if not self.longpoll.get('server'):
            self.initLongpoll()
        if not self.longpoll:
            return []
        url = 'https://{}?act=a_check&key={}&ts={}&wait=25&mode={}&version={}'.format(
            self.longpoll['server'], self.longpoll['key'], self.longpoll['ts'], mode, self.longpoll_version)
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
        if not self.login_params or '@' in self.login_params['username']:
            logger.critical("I don't know your phone number")
            raise VkError('Phone number required')
        page = urllib.request.urlopen(url).read().decode()
        url_re = re.compile(r'/(login.php\?act=security_check&[^"]+)"')
        post_url = 'https://m.vk.com/' + url_re.search(page).group(1)
        phone = self.login_params['username'][-10:-2]
        urllib.request.urlopen(post_url, ('code=' + phone).encode('utf-8'))

    def uploadMessagePhoto(self, paths):
        if isinstance(paths, str):
            paths = [paths]
        server = self.photos.getMessagesUploadServer()
        result = []
        with self.delayed() as dm:
            for path in paths:
                resp = uploadFile(server['upload_url'], path, 'photo')
                self.writeLog('uploading photo {} to {}\nresponse: {}'.format(path, server['upload_url'], resp))
                if resp['photo'] != '[]':
                    dm.photos.saveMessagesPhoto(photo=resp['photo'], server=resp['server'], hash=resp['hash']).set_callback(lambda a, b: result.extend(b or []))
        return result

    def delayed(self, *, max_calls=MAX_CALLS_IN_EXECUTE):
        return DelayedManager(self, max_calls)

