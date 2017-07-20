import logging
import threading
import time
from collections import defaultdict

logger = logging.getLogger('cache')

class Cache:
    def __init__(self, api, invalidate_interval=0):
        self.api = api
        self.objects = {}
        self.lock = threading.RLock()
        self.invalidate_interval = invalidate_interval

    def __getitem__(self, uid):
        uid = int(uid)
        try:
            with self.lock:
                if uid not in self.objects or (self.objects[uid][0] + self.invalidate_interval < time.time() and self.invalidate_interval):
                    self.load([uid])
                if uid in self.objects:
                    return self.objects[uid][1]
                else:
                    return None
        except Exception:
            logger.exception('Cache error')
            return None

    def __delitem__(self, uid):
        uid = int(uid)
        with self.lock:
            if uid in self.objects:
                del self.objects[uid]

    def clear(self):
        with self.lock:
            self.objects = {}

    def gc(self):
        with self.lock:
            t = time.time()
            for uid in list(self.objects):
                if self.objects[uid][0] + self.invalidate_interval < t:
                    del self.objects[uid]

    def load(self, ids, clean=False):
        ids = list(map(int, ids))
        try:
            to_get = []
            with self.lock:
                ctime = time.time()
                for uid in ids:
                    if uid > 0 and (clean or uid not in self.objects or self.objects[uid][0] + self.invalidate_interval - 5 < ctime):
                        to_get.append(uid)
                if to_get:
                    resp = self._load(to_get)
                    for obj in resp:
                        self.objects[obj['id']] = (ctime, obj)
        except Exception:
            logger.exception('Cache error')

    def _load(self, ids):
        raise NotImplementedError()

class UserCache(Cache):
    def __init__(self, api, fields, invalidate_interval=0):
        super().__init__(api, invalidate_interval)
        self.fields = fields
        if ',' in fields and 'id' in fields.split(','):
            l = fields.split(',')
            l.remove('id')
            self.fields = ','.join(l)

    def _load(self, ids):
        return self.api.users.get(user_ids=','.join(map(str, ids)), fields=self.fields)

class ConfCache(Cache):
    def __init__(self, api, self_id=0, invalidate_interval=0):
        super().__init__(api, invalidate_interval)
        self.self_id = self_id

    def _load(self, ids):
        r = self.api.messages.getChat(chat_ids=','.join(map(str, ids)), fields='id') or []
        for conf in r:
            for user in conf['users']:
                if user['id'] == self.self_id:
                    conf['invited_by'] = user['invited_by']
                    break
            else:
                conf['invited_by'] = 0
            del conf['users']
        return r

class MessageCache:
    def __init__(self):
        self.user_msg = {}
        self.sender_msg = {}

    def add(self, sender, message, mid, reply):
        entry = {'id': mid, 'text': message['body'], 'reply': reply, 'count': 1, 'time': time.time(), 'user_id': message['user_id']}
        self.user_msg[message['user_id']] = entry
        self.sender_msg[sender] = entry
        return entry

    def byUser(self, uid):
        return self.user_msg.setdefault(uid, {})

    def bySender(self, pid):
        return self.sender_msg.setdefault(pid, {})

    def updateTime(self, sender, newtime=None):
        if newtime is None:
            newtime = time.time()
        self.sender_msg.setdefault(sender, {})['time'] = newtime

    def dump(self):
        messages = {id(i): i.copy() for i in self.user_msg.values()}
        messages.update({id(i): i.copy() for i in self.sender_msg.values()})
        um = {i: id(self.user_msg[i]) for i in self.user_msg}
        sm = {i: id(self.sender_msg[i]) for i in self.sender_msg}
        return {'messages': messages, 'user': um, 'sender': sm}

    def load(self, data):
        self.user_msg = {int(i): data['messages'][str(j)] for i, j in data['user'].items()}
        self.sender_msg = {int(i): data['messages'][str(j)] for i, j in data['sender'].items()}


class LimiterCache:

    def __init__(self, config_file):
        self.data = defaultdict(dict)
        self.intervals = {}
        self.config_file = config_file
        self.reload()

    def reload(self):
        with open(self.config_file) as f:
            lines = filter(str.strip, f.readlines())
            self.intervals = {limit: int(interval) for limit, interval in map(str.split, lines)}

    def add(self, pid, limiters):
        t = time.time()
        for l in limiters.split():
            self.data[pid][l[1:]] = t

    def get(self, pid):
        t = time.time()
        res = []
        for l in self.data[pid]:
            if l not in self.intervals:
                logger.error('Unknown limiter: ' + l)
            elif self.data[pid][l] + self.intervals[l] > t:
                res.append(l)
        return ' '.join('@' + i for i in res)
