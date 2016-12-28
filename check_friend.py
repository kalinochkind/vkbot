import time

default_fields = 'photo_50,country'

checks = [
    (lambda self, fr: fr['id'] not in self.noadd, 'Ignored'),
    (lambda self, fr: 'deactivated' not in fr, 'Account is deactivated'),
    (lambda self, fr: fr['photo_50'] and not fr['photo_50'].endswith('camera_50.png'), 'No avatar'),
    (lambda self, fr: fr.get('country', {'id': 0})['id'] in [0, 1, 2, 3], 'Bad country'),
    (lambda self, fr: all(i in self.allowed for i in fr['first_name'] + fr['last_name']), 'Bad characters in name'),
    (lambda self, fr: not fr.get('last_seen') or time.time() - fr['last_seen']['time'] < 3600 * 24 * self.offline_allowed, 'Offline too long'),
    (lambda self, fr: not any(i in (fr['first_name'] + ' ' + fr['last_name']).lower() for i in self.banned_substrings), 'Bad substring in name'),
    (lambda self, fr: fr['first_name'] != fr['last_name'], 'First name equal to last name'),
]

class FriendController:

    def __init__(self, params, ignore_filename, allowed_names_filename):
        self.ignore_filename = ignore_filename
        self.allowed_filename = allowed_names_filename
        self.noadd = set(map(int, open(ignore_filename).read().split()))
        line1, line2 = open(allowed_names_filename, encoding='utf-8').readlines()
        self.allowed = set(line1 + ' ')
        self.banned_substrings = line2.split()
        self.offline_allowed = params.get('offline_allowed', 0)
        self.add_everyone = params.get('add_everyone', False)
        self.fields = self.requiredFields(params)

    @staticmethod
    def requiredFields(params):
        if params.get('add_everyone', False):
            # there should be no fields here
            # but VK returns just a list of ids if no fields are requested
            # so this is a dirty hack
            return 'id'
        return default_fields + (',last_seen' if params.get('offline_allowed') else '')

    def writeNoadd(self):
        with open(self.ignore_filename, 'w') as f:
            f.write('\n'.join(map(str, sorted(self.noadd))))

    def appendNoadd(self, users):
        self.noadd.update(users)
        with open(self.ignore_filename, 'a') as f:
            f.write('\n' + '\n'.join(map(str, sorted(users))))

    def isGood(self, fr, need_reason=False):
        reasons = []
        for fun, msg in (checks[:1] if self.add_everyone else checks):
            if not fun(self, fr):
                if need_reason:
                    reasons.append(msg.lower() if reasons else msg)
                else:
                    return False
        if need_reason:
            return ', '.join(reasons) or None
        else:
            return True
