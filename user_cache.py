import config
import time
import log

class user_cache:

    invalidate_interval = config.get('user_cache.invalidate_interval')

    def __init__(self, api, fields):
        self.api = api
        self.fields = fields
        self.users = {}

    def load(self, uid):
        uid = list(map(int, uid))

        try:
            to_get = []
            ctime = time.time()
            for user in uid:
                if user > 0 and (user not in self.users or self.users[user][0] + self.invalidate_interval - 5 < ctime):
                    to_get.append(user)
            if to_get:
                resp = self.api.users.get(user_ids=','.join(map(str, to_get)), fields=self.fields)
                for user in resp:
                    self.users[user['id']] = (ctime, user)
        except Exception:
            log.error('user_cache error', True)
            return None

    def __getitem__(self, uid):
        uid = int(uid)
        try:
            if uid not in self.users or self.users[uid][0] + self.invalidate_interval < time.time():
                self.load([uid])
            return self.users[uid][1]
        except Exception:
            log.error('user_cache error', True)
            return None

    def __delitem__(self, uid):
        uid = int(uid)
        if uid in self.users:
            del self.users[uid]

    def clear(self):
        self.users = {}
