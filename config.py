import sys
import configparser
import accounts

cp_global = configparser.ConfigParser()
cp_global.read('data/inf.cfg')
cp_local = configparser.ConfigParser()
cp_local.read(accounts.getFile('inf.cfg'))

def get(param, type='s'):
    param = param.split('.')
    if param[0] in cp_local and param[1] in cp_local[param[0]]:
        cp = cp_local
    else:
        cp = cp_global
    if type == 's':
        return cp[param[0]].get(param[1])
    elif type == 'i':
        return cp[param[0]].getint(param[1])
    elif type == 'f':
        return cp[param[0]].getfloat(param[1])
    elif type == 'b':
        return cp[param[0]].getboolean(param[1])
