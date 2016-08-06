import config
import time
import log
import threading


class Cache:

    invalidate_interval = 0

    def __init__(self, api):
        self.api = api
        self.objects = {}
        self.lock = threading.RLock()

    def __getitem__(self, uid):
        uid = int(uid)
        try:
            with self.lock:
                if uid not in self.objects or self.objects[uid][0] + self.invalidate_interval < time.time():
                    self.load([uid])
                return self.objects[uid][1]
        except Exception:
            log.error('Cache error', True)
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
                for id in ids:
                    if id > 0 and (clean or id not in self.objects or self.objects[id][0] + self.invalidate_interval - 5 < ctime):
                        to_get.append(id)
                if to_get:
                    resp = self._load(to_get)
                    for obj in resp:
                        self.objects[obj['id']] = (ctime, obj)
        except Exception:
            log.error('Cache error', True)

    def _load(self, ids):
        raise NotImplementedError()


class UserCache(Cache):

    invalidate_interval = config.get('cache.user_invalidate_interval', 'i')

    def __init__(self, api, fields):
        super().__init__(api)
        self.fields = fields

    def _load(self, ids):
        return self.api.users.get(user_ids=','.join(map(str, ids)), fields=self.fields)


class ConfCache(Cache):

    invalidate_interval = config.get('cache.conf_invalidate_interval', 'i')

    def _load(self, ids):
        return self.api.messages.getChat(chat_ids=','.join(map(str, ids)))
