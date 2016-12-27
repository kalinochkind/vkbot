import time

import accounts
import config
import stats

fields = 'photo_50,country,last_seen'

noadd = set(map(int, open(accounts.getFile('noadd.txt')).read().split()))

line1, line2 = open(accounts.getFile('allowed.txt'), encoding='utf-8').readlines()
allowed = set(line1 + ' ')
banned_substrings = line2.split()

offline_allowed = config.get('check_friend.offline_allowed', 'i')
add_everyone = config.get('vkbot.add_everyone')

def writeNoadd():
    with open(accounts.getFile('noadd.txt'), 'w') as f:
        f.write('\n'.join(map(str, sorted(noadd))))
    stats.update('ignored', len(noadd))

def appendNoadd(users):
    noadd.update(users)
    with open(accounts.getFile('noadd.txt'), 'a') as f:
        f.write('\n' + '\n'.join(map(str, sorted(users))))
    stats.update('ignored', len(noadd))

checks = [
    (lambda fr: fr['id'] not in noadd, 'Ignored'),
    (lambda fr: 'deactivated' not in fr, 'Account is deactivated'),
    (lambda fr: fr['photo_50'] and not fr['photo_50'].endswith('camera_50.png'), 'No avatar'),
    (lambda fr: fr.get('country', {'id': 0})['id'] in [0, 1, 2, 3], 'Bad country'),
    (lambda fr: all(i in allowed for i in fr['first_name'] + fr['last_name']), 'Bad characters in name'),
    (lambda fr: not fr.get('last_seen') or time.time() - fr['last_seen']['time'] < 3600 * 24 * offline_allowed, 'Offline too long'),
    (lambda fr: not any(i in (fr['first_name'] + ' ' + fr['last_name']).lower() for i in banned_substrings), 'Bad substring in name'),
    (lambda fr: fr['first_name'] != fr['last_name'], 'First name equal to last name'),
]

def isGood(fr, need_reason=False):
    reasons = []
    for fun, msg in (checks[:1] if add_everyone else checks):
        if not fun(fr):
            if need_reason:
                reasons.append(msg.lower() if reasons else msg)
            else:
                return False
    if need_reason:
        return ', '.join(reasons) or None
    else:
        return True
