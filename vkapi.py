import threading
import urllib.request
import urllib.parse
import json
import time
import sys
import socket
import config

class vk_api:
    logging = config.get('vkapi.logging')
    checks_before_antigate = config.get('vkapi.checks_before_antigate')
    captcha_check_interval = config.get('vkapi.captcha_check_interval')

    def __init__(self, username, password, timeout=config.get('vkapi.default_timeout')):
        self.username = username
        self.password = password
        self.captcha_delayed = 0
        self.captcha_handler = None
        self.token = None
        self.callback = None
        self.delayed_list = []
        self.max_delayed = 25
        self.timeout = timeout
        self.longpoll_server = ''
        self.longpoll_key = ''
        self.longpoll_ts = 0
        self.api_lock = threading.RLock()
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
                        return handler.apiCall(self.method, dp)
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
        return self.apiCall('execute', {"code": code})

    def encodeApiCall(self, s):
        return "API." + s[0] + '(' + str(s[1]).replace('"', '\\"').replace("'", '"') + ')'

    def sync(self):
        if not self.delayed_list:
            return
        if len(self.delayed_list) == 1:
            response = self.apiCall(*self.delayed_list[0])
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

    def apiCall(self, method, params, retry=0):
        with self.api_lock:
            params['v'] = '5.40'
            url = 'https://api.vk.com/method/' + method + '?' + urllib.parse.urlencode(params) + '&access_token=' + self.getToken()
            last_get = time.time()
            try:
                json_string = urllib.request.urlopen(url, timeout=self.timeout).read()
            except socket.timeout:
                print('[WARNING] timeout')
                time.sleep(1)
                return self.apiCall(method, params)
            except Exception as e:
                if retry:
                    print('[ERROR] (%s) %s: %s' % (method, e.__class__.__name__, str(e)))
                    return None
                else:
                    time.sleep(1)
                    print('[WARNING] (%s) %s: %s, retrying' % (method, e.__class__.__name__, str(e)))
                    return self.apiCall(method, params, 1)
            data_array = json.loads(json_string.decode('utf-8'))
            if self.logging:
                with open('inf.log', 'a') as f:
                    print('method: %s, params: %s' % (method, json.dumps(params)), file=f)
                    print('response: %s\n' % json.dumps(data_array), file=f)
            duration = round((time.time() - last_get), 2)
            if duration > 2:
                print('[WARNING] ' + method + ' fucks up. Ping is ' + str(duration) + ' seconds' )
            time.sleep(max(0, last_get - time.time() + 0.4))
            if 'response' in data_array:
                self.captcha_delayed = 0
                return data_array['response']
            elif 'error' in data_array:
                if data_array['error']['error_code'] == 14: #Captcha needed
                    if self.captcha_delayed == self.checks_before_antigate and self.captcha_handler:
                        print('Using antigate')
                        ans = self.captcha_handler(data_array['error']['captcha_img'], self.timeout)
                        if ans is None:
                            time.sleep(1)
                        else:
                            params['captcha_sid'] = data_array['error']['captcha_sid']
                            params['captcha_key'] = ans
                            self.captcha_delayed = 0
                    else:
                        if not self.captcha_delayed:
                            print('[ERROR] Captcha needed')
                        time.sleep(self.captcha_check_interval)
                        self.captcha_delayed += 1
                    return self.apiCall(method, params)
                elif data_array['error']['error_code'] == 5: #Auth error
                    self.login()
                    return self.apiCall(method, params)
                elif data_array['error']['error_code'] == 900: #Black list
                    print('[ERROR] Banned')
                    return None
                elif data_array['error']['error_code'] == 7:
                    if retry:
                        print('[ERROR] Banned')
                        return None
                    else:
                        print('[ERROR] Banned, retrying')
                        time.sleep(3)
                        return self.apiCall(method, params, 1)
                elif data_array['error']['error_code'] == 10:
                    if retry:
                        print('[ERROR] Unable to reply')
                        return None
                    else:
                        print('[ERROR] Unable to reply, retrying')
                        time.sleep(3)
                        return self.apiCall(method, params, 1)
                else:
                    print('[ERROR] Code {}: {}'.format(data_array['error']['error_code'], data_array['error'].get('error_msg')))
                    return None
            else:
                return self.apiCall(method, params)

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
        except socket.timeout:
            print('[ERROR] longpoll timeout')
            time.sleep(1)
            return []
        data_array = json.loads(json_string.decode('utf-8'))
        if 'ts' in data_array:
            self.longpoll_ts = data_array['ts']
        if 'updates' in data_array:
            return data_array['updates']
        elif data_array['failed'] != 1:
            self.initLongpoll()
            return []
        else:
            return self.getLongpoll(mode)
