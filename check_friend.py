import time
import config
import accounts

fields = 'photo_50,country,last_seen'

s = open(accounts.getFile('allowed.txt'), encoding='utf-8').readlines()
noadd = set(map(int, open(accounts.getFile('noadd.txt')).read().split()))
allowed = set(s[0] + ' ')
s = s[1].split()

offline_allowed = config.get('check_friend.offline_allowed', 'i')

def writeNoadd():
    with open(accounts.getFile('noadd.txt'), 'w') as f:
        f.write('\n'.join(map(str, sorted(noadd))))

def appendNoadd(users):
    noadd.update(users)
    with open(accounts.getFile('noadd.txt'), 'a') as f:
        f.write('\n' + '\n'.join(map(str, sorted(users))))

def check_char(c):
    return c in allowed

checks = [
(lambda fr:'deactivated' not in fr, 'Account is deactivated'),
(lambda fr:fr['photo_50'] and not fr['photo_50'].endswith('camera_50.png'), 'No avatar'),
(lambda fr:fr.get('country', {'id':0})['id'] in [0, 1, 2, 3], 'Bad country'),
(lambda fr:all(check_char(i) for i in fr['first_name'] + fr['last_name']), 'Bad characters in name'),
(lambda fr:'last_seen' in fr and time.time() - fr['last_seen']['time'] < 3600 * 24 * offline_allowed, 'Offline too long'),
(lambda fr:not any(i in (fr['first_name'] + ' ' + fr['last_name']).lower() for i in s), 'Bad substring in name'),
(lambda fr:fr['id'] not in noadd, 'Ignored'),
(lambda fr:fr['first_name'] != fr['last_name'], 'First name equal to last name'),
]

def is_good(fr, need_reason=False):
    reasons = []
    for fun, msg in checks:
        if not fun(fr):
            if need_reason:
                reasons.append(msg.lower() if reasons else msg)
            else:
                return False
    if need_reason:
        return ', '.join(reasons) or None
    else:
        return True
