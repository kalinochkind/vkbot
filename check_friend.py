import time
import config

fields = 'photo_50,country,last_seen'

s = open('allowed.txt', encoding='utf-8').readlines()
noadd = set(map(int, open('noadd.txt').read().split()))
allowed = set(s[0] + ' ')
s = s[1].split()

offline_allowed = config.get('check_friend.offline_allowed')

def writeNoadd():
    with open('noadd.txt', 'w') as f:
        f.write('\n'.join(map(str, sorted(noadd))))

def check_char(c):
    return c in allowed

def is_good(fr):
    now = int(time.time())
    return (('deactivated' not in fr) and 
            fr['photo_50'] and not fr['photo_50'].endswith('camera_50.png') and 
            fr.get('country', {'id':0})['id'] in [0, 1, 2, 3] and 
            all(check_char(i) for i in fr['first_name'] + fr['last_name']) and
            now - fr['last_seen']['time'] < 3600 * 24 * offline_allowed and
            not any(i in (fr['first_name'] + ' ' + fr['last_name']).lower() for i in s) and
            fr['id'] not in noadd
            )
