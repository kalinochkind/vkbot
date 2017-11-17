import time

def check(desc, fields=''):
    def fn(func):
        func.desc = desc
        func.fields = fields.split(',') if fields else []
        return func
    return fn

class Checks:
    @check('Ignored')
    def ignored(fc, guy, args):
        return guy['id'] not in fc.noadd

    @check('Account is deactivated')
    def deactivated(fc, guy, args):
        return 'deactivated' not in guy

    @check('No avatar', 'photo_50')
    def noavatar(fc, guy, args):
        return guy['photo_50'] and not guy['photo_50'].endswith('camera_50.png')

    @check('Bad country', 'country')
    def country(fc, guy, args):
        return str(guy.get('country', {'id': 0})['id']) in ['0'] + args

    @check('Bad characters in name')
    def namechars(fc, guy, args):
        return all(i in fc.allowed for i in guy['first_name'] + guy['last_name'])

    @check('Offline too long', 'last_seen')
    def offline(fc, guy, args):
        return not guy.get('last_seen') or time.time() - guy['last_seen']['time'] < 3600 * 24 * int(args[0])

    @check('Bad substring in name')
    def namesubstr(fc, guy, args):
        return not any(i in (guy['first_name'] + ' ' + guy['last_name']).lower() for i in fc.banned_substrings)

    @check('First name equal to last name')
    def equalnames(fc, guy, args):
        return guy['first_name'] != guy['last_name']

class FriendController:
    def __init__(self, params, ignore_filename, allowed_names_filename, bots_filename):
        self.ignore_filename = ignore_filename
        self.allowed_filename = allowed_names_filename
        try:
            self.bots = set(map(int, open(bots_filename).read().split()))
        except FileNotFoundError:
            self.bots = set()
        self.noadd = set(map(int, open(ignore_filename).read().split()))
        line1, line2 = open(allowed_names_filename, encoding='utf-8').readlines()
        self.allowed = set(line1 + ' ')
        self.banned_substrings = line2.split()
        self.params = params
        self.params.update({'ignored': ''})
        self.fields = self.requiredFields(params)

    @staticmethod
    def requiredFields(params):
        fields = sum([getattr(Checks, i).fields for i in params], [])
        return ','.join(fields) or 'id'

    def writeNoadd(self):
        with open(self.ignore_filename, 'w') as f:
            f.write('\n'.join(map(str, sorted(self.noadd))))

    def appendNoadd(self, users):
        self.noadd.update(users)
        with open(self.ignore_filename, 'a') as f:
            f.write('\n' + '\n'.join(map(str, sorted(users))))

    def isGood(self, fr, need_reason=False):
        reasons = []
        for fname in self.params:
            fun = getattr(Checks, fname)
            if not fun(self, fr, self.params[fname].split()):
                if need_reason:
                    reasons.append(fun.desc.lower() if reasons else fun.desc)
                else:
                    return False
        if need_reason:
            return ', '.join(reasons) or None
        else:
            return True
