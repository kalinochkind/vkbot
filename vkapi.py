import ssl
from functools import wraps

def sslwrap(func):
    @wraps(func)
    def bar(*args, **kw):
        kw['ssl_version'] = ssl.PROTOCOL_TLSv1
        return func(*args, **kw)
    return bar

ssl.wrap_socket = sslwrap(ssl.wrap_socket)

import urllib.request
import urllib.parse
import json
import time
import sys
from socket import timeout

class vk_api:
    path = 'https://api.vk.com/method/'
    logging = 0
    captcha_delayed = 0
    captcha_handler = None
    checks_before_antigate = 6
    captcha_check_interval = 5
    token = None
    max_delayed = 25
    callback = None
    delayed_list = None

    def __init__(self, username, password, timeout=5):
        self.username = username
        self.password = password
        self.delayed_list = []
        self.guid = int(time.time() * 5)
        self.timeout = timeout
        self.getToken()

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
                        return handler.apiCall(dict(method=self.method, **dp))
                    def delayed(self, **dp):
                        if len(handler.delayed_list) >= handler.max_delayed:
                            handler.sync()
                        handler.delayed_list.append((self.method, dp.copy()))
                return _method_wrapper(self.group + '.' + item)
        if item not in ['users', 'auth', 'wall', 'photos', 'friends', 'widgets', 'storage', 'status', 'audio', 'pages',
                    'groups', 'board', 'video', 'notes', 'places', 'account', 'messages', 'newsfeed', 'likes', 'polls',
                    'docs', 'fave', 'notifications', 'stats', 'search', 'apps', 'utils', 'database', 'gifts']:
            raise AttributeError(item)
        return _group_wrapper(item)

    def delayedReset(self, max_delayed=25, callback=None):
        self.sync()
        self.max_delayed = max_delayed
        self.callback = callback

    def execute(self, code):
        return self.apiCall({"method": "execute", "code": code})

    def encodeApiCall(self, s):
        return "API." + s[0] + '(' + str(s[1]).replace('"', '\\"').replace("'", '"') + ')'

    def sync(self):
        if not self.delayed_list:
            return
        if len(self.delayed_list) == 1:
            response = self.apiCall(dict(method=self.delayed_list[0][0], **self.delayed_list[0][1]))
            if self.callback:
                self.callback(self.delayed_list[0], response)
            self.delayed_list.clear()
            return
        query = ['return[']
        for num, i in enumerate(self.delayed_list):
            query.append(self.encodeApiCall(i) + ',')
        query.append('];')
        query = ''.join(query)
        response = self.execute(query)
        if self.callback:
            for i in zip(self.delayed_list, response):
                self.callback(*i)
        self.delayed_list.clear()

    def apiCall(self, params):
        last_get = time.time()
        method = params['method']
        del params['method']
        params['v'] = '5.37'
        url = self.path + method + '?' + urllib.parse.urlencode(params) + '&access_token=' + self.getToken()
        try:
            json_string = urllib.request.urlopen(url, timeout=self.timeout).read()
        except timeout:
            print('[ERROR] timeout')
            time.sleep(1)
            params['method'] = method
            return self.apiCall(params)
        data_array = json.loads(json_string.decode('utf-8'))
        if self.logging:
            with open('inf.log', 'a') as f:
                print('method: %s, params: %s' % (method, json.dumps(params)), file=f)
                print('response: %s\n' % json.dumps(data_array), file=f)
        duration = round((time.time() - last_get), 2)
        if duration > 2:
            print('[WARNING] ' + method + ' fucks up. Ping is ' + str(duration) + ' seconds' )
        time.sleep(0.35)
        if 'response' in data_array:
            self.captcha_delayed = 0
            return data_array['response']
        elif 'error' in data_array:
            if data_array['error']['error_code'] == 14: #Captcha needed
                params['method'] = method
                if self.captcha_delayed == self.checks_before_antigate and self.captcha_handler:
                    print('Using antigate')
                    ans = self.captcha_handler(data_array['error']['captcha_img'], self.timeout)
                    if ans is None:
                        time.sleep(self.sleep_on_captcha)
                    else:
                        params['captcha_sid'] = data_array['error']['captcha_sid']
                        params['captcha_key'] = ans
                        self.captcha_delayed = 0
                else:
                    if not self.captcha_delayed:
                        print('[ERROR] Captcha needed')
                    time.sleep(self.captcha_check_interval)
                    self.captcha_delayed += 1
                return self.apiCall(params)
            elif data_array['error']['error_code'] == 5: #Auth error
                self.login()
                params['method'] = method
                return self.apiCall(params)
            elif data_array['error']['error_code'] == 7: #Black list
                print('[ERROR] Banned')
                return None
            elif data_array['error']['error_code'] == 10:
                print('[ERROR] Unable to reply')
                return None
        else:
            params['method'] = method
            return self.apiCall(params)

    def login(self):
        print('Fetching new token')
        url = 'https://oauth.vk.com/token?grant_type=password&client_id=2274003&client_secret=hHbZxrka2uZ6jB1inYsH&username=' + self.username + '&password=' + self.password
        try:
            json_string = urllib.request.urlopen(url).read().decode()
        except Exception:
            print('[FATAL] Authorization failed')
            sys.exit(0)
        data = json.loads(json_string)
        self.token = data['access_token']
        with open('token.txt', 'w') as f:
            f.write(self.token)

    def getToken(self):
        if not self.token:
            try:
                self.token = open('token.txt').read().strip()
            except FileNotFoundError:
                self.token = ''
        return self.token
