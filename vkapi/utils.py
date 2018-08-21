import logging
import threading
import time


TYPING_INTERVAL = 5
CONF_START = 2000000000
VK_METHOD_GROUPS = {'account', 'ads', 'apps', 'audio', 'auth', 'board', 'database', 'docs', 'fave', 'friends', 'gifts', 'groups', 'leads', 'likes',
    'market', 'messages', 'newsfeed', 'notes', 'notifications', 'pages', 'photos', 'places', 'polls', 'search', 'stats', 'status', 'storage',
    'users', 'utils', 'video', 'wall', 'widgets'}

logger = logging.getLogger('vkapi')


class DelayedCall:
    def __init__(self, dispatcher, method, params):
        self.dispatcher = dispatcher
        self.method = method
        self.params = params
        self._lock = threading.Lock()
        self._callback_func = None
        self._value = None
        self._computed = False

    def _set_value(self, value):
        with self._lock:
            self._value = value
            self._computed = True
            if self._callback_func is not None:
                self._do_callback()

    def _do_callback(self):
        self._callback_func(self.params, self._value)

    def set_callback(self, func):
        with self._lock:
            self._callback_func = func
            if self._computed:
                self._do_callback()
        return self

    def walk(self, func):
        def cb(req, resp):
            func(req, resp)
            if resp is None:
                return
            if 'next_from' in resp:
                if resp['next_from']:
                    req['start_from'] = resp['next_from']
                    self.dispatcher._callMethod(self.method, req).set_callback(cb)
            elif 'count' in resp and 'count' in req and req['count'] + req.get('offset', 0) < resp['count']:
                req['offset'] = req.get('offset', 0) + req['count']
                self.dispatcher._callMethod(self.method, req).set_callback(cb)
        self.set_callback(cb)
        return self


class VkMethodDispatcher:

    class _GroupWrapper:
        def __init__(self, group, dispatcher):
            self.group = group
            self.dispatcher = dispatcher

        def __getattr__(self, subitem):
            def call(**kwargs):
                return self.dispatcher._callMethod(self.group + '.' + subitem, kwargs)
            return call

    def __getattr__(self, item):
        if item not in VK_METHOD_GROUPS:
            raise AttributeError(item)
        return self._GroupWrapper(item, self)

    def _callMethod(self, method, kwargs):
        raise NotImplementedError


class DelayedManager(VkMethodDispatcher):
    def __init__(self, api, max_calls):
        self.api = api
        self.max_calls = max_calls
        self.queue = []
        self._lock = threading.Lock()


    def _callMethod(self, method, kwargs):
        call = DelayedCall(self, method, kwargs)
        old_queue = None
        with self._lock:
            self.queue.append(call)
            if len(self.queue) >= self.max_calls:
                old_queue = self.queue
                self.queue = []
        if old_queue:
            self._do_execute(old_queue)
        return call

    def _do_execute(self, methods):
        if len(methods) == 1:
            call = methods[0]
            response = self.api.apiCall(call.method, call.params)
            call._set_value(response)
            return
        query = ['return[']
        for num, i in enumerate(methods):
            query.append(self.api.encodeApiCall(i.method, i.params) + ',')
        query.append('];')
        query = ''.join(query)
        response = self.api.execute(query)
        errors = response.get('execute_errors', [])
        for call, r in zip(methods, response['response']):
            if r is False:  # it's fine here
                error = errors.pop(0)
                if error['method'] != call.method:
                    logger.error('Failed to match errors with methods. Response: ' + str(response))
                    return
                if self.api.processError(call.method, call.params, {'error': error}):
                    call.params['_retry'] = True
                    self._callMethod(call.method, call.params)
                else:
                    call._set_value(None)
            else:
                call._set_value(r)

    def sync(self):
        while True:
            with self._lock:
                if not self.queue:
                    break
                old_queue = self.queue
                self.queue = []
            self._do_execute(old_queue)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.sync()


class LongpollMessage:
    def __init__(self, record):
        self.mid, self.flags, self.sender, self.ts, self.text, self.opt, self.extra = record

class VkError(Exception):
    pass

def getSender(message):
    if 'chat_id' in message:
        return CONF_START + message['chat_id']
    return message['user_id']


class RateLimiter:

    def __init__(self, interval):
        self.last_call = 0
        self.interval = interval
        self.lock = threading.RLock()

    def __enter__(self):
        self.lock.acquire()
        now = time.time()
        if self.last_call + self.interval > now:
            time.sleep(self.last_call + self.interval - now)
            now = time.time()
        self.last_call = now

    def __exit__(self, *args):
        self.lock.release()
