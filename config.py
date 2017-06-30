import configparser
import sys

import accounts

cp = None

def get(param, typename='s'):
    global cp
    if not cp:
        cp = configparser.ConfigParser()
        cp.read(accounts.getFile('inf.cfg'))
    param = param.split('.')
    try:
        if typename == 'b':
            return cp[param[0]].getboolean(param[1])
        # noinspection PyStatementEffect
        cp[param[0]][param[1]]  # to make sure that it exists
        if typename == 's':
            return cp[param[0]].get(param[1])
        elif typename == 'i':
            return cp[param[0]].getint(param[1])
        elif typename == 'f':
            return cp[param[0]].getfloat(param[1])
    except KeyError:
        if input('Parameter {}.{} does not exist. Rebuild configuration? [y/n] '.format(*param)).lower() == 'y':
            rebuild(accounts.getFile('inf.cfg'), accounts.default_config)
        sys.exit()

def rebuild(current, default):
    old = configparser.ConfigParser()
    old.read(current)
    new = configparser.ConfigParser()
    new.read(default)
    new.add_section('login')
    new['login']['login'] = ''
    new['login']['password'] = ''
    for section in new:
        for key in new[section]:
            try:
                new[section][key] = old[section][key]
                del old[section][key]
                if not list(old[section]):
                    del old[section]
            except KeyError:
                print('{}.{} not found, using default value "{}"'.format(section, key, new[section][key]))
    with open(current, 'w') as f:
        new.write(f)
    with open(current + '.old', 'w') as f:
        old.write(f)
    old_keys = [s + '.' + k for s in old for k in old[s]]
    if old_keys:
        print('Deleted keys have been saved to {}.old ({})'.format(current, ', '.join(old_keys)))
