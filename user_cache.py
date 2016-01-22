import config
import time

class user_cache:
    
    invalidate_interval = config.get('user_cache.invalidate_interval')
    
    def __init__(self, api, fields):
        self.api = api
        self.fields = fields
        self.users = {}
        
    def __getitem__(self, uid):
        uid = int(uid)
        try:
            if uid not in self.users or self.users[uid][0] + self.invalidate_interval < time.time():
                self.users[uid] = (time.time(), self.api.users.get(user_ids=uid, fields=self.fields)[0])
            return self.users[uid][1]
        except Exception:
            return None

    def __delitem__(self, uid):
        uid = int(uid)
        if uid in self.users:
            del self.users[uid]

    def clear(self):
        self.users = {}
