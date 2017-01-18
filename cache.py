import logging
import threading
import time

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
                if uid not in self.objects or self.objects[uid][0] + self.invalidate_interval < time.time():
                    self.load([uid])
                return self.objects[uid][1]
        except Exception:
            logging.exception('Cache error')
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
            logging.exception('Cache error')

    def _load(self, ids):
        raise NotImplementedError()

class UserCache(Cache):
    def __init__(self, api, fields, invalidate_interval=0):
        super().__init__(api, invalidate_interval)
        self.fields = fields

    def _load(self, ids):
        return self.api.users.get(user_ids=','.join(map(str, ids)), fields=self.fields)

class ConfCache(Cache):
    def _load(self, ids):
        return self.api.messages.getChat(chat_ids=','.join(map(str, ids)))

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
