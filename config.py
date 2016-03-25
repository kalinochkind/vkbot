import configparser
import accounts

cp = configparser.ConfigParser()
cp.read(accounts.getFile('inf.cfg'))

def get(param, type='s'):
    param = param.split('.')
    if type == 's':
        return cp[param[0]].get(param[1])
    elif type == 'i':
        return cp[param[0]].getint(param[1])
    elif type == 'f':
        return cp[param[0]].getfloat(param[1])
    elif type == 'b':
        return cp[param[0]].getboolean(param[1])
