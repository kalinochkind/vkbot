import time

fields = 'photo_50,country,last_seen'

allowed = set(open('allowed.txt').read() + ' ')

def check_char(c):
    return c in allowed

def is_good(fr):
    now = int(time.time())
    return (('deactivated' not in fr) and 
            not fr['photo_50'].endswith('camera_50.png') and 
            fr.get('country', {'id':0})['id'] in [0, 1, 2, 3] and 
            all(check_char(i) for i in fr['first_name'] + fr['last_name']) and
            now - fr['last_seen']['time'] < 3600 * 24 * 14
            )
