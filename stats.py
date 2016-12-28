import json
import threading

import accounts

lock = threading.Lock()
_stats = None

def _load():
    global _stats
    if _stats is None:
        try:
            _stats = json.loads(open(accounts.getFile('stats.txt')).read())
        except Exception:
            _stats = {}

def update(name, value):
    with lock:
        _load()
        if name in _stats and _stats[name] == value:
            return
        _stats[name] = value
        with open(accounts.getFile('stats.txt'), 'w') as f:
            f.write(json.dumps(_stats))

def get(name, default=None):
    with lock:
        _load()
        return _stats.get(name, default)
