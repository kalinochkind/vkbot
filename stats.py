import json
import accounts


try:
    _stats = json.loads(open(accounts.getFile('stats.txt')).read())
except Exception:
    _stats = {}

def update(name, value):
    if name in _stats and _stats[name] == value:
        return
    _stats[name] = value
    with open(accounts.getFile('stats.txt'), 'w') as f:
        f.write(json.dumps(_stats))

def get(name, default=None):
    return _stats.get(name, default)
