import os
import args
import sys
import getpass

account_files = ['banned.txt', 'captcha.txt', 'noadd.txt', 'token.txt']
current_account = None


def forceInput(text, password=False):
    s = ''
    while not s.strip():
        s = getpass.getpass(text) if password else input(text)
    return s

def validateName(name):
    return name and len(name) <= 256 and not any(i in name for i in './\\ ')

def createAccount(name):
    login = forceInput('Login for {}: '.format(name))
    password = forceInput('Password for {}: '.format(name), True)
    dirname = 'accounts/' + name + '/'
    os.mkdir(dirname)
    for i in account_files:
        open(dirname + i, 'w').close()
    with open(dirname + 'inf.cfg', 'w') as f:
        f.write(open('inf.cfg.default').read().strip() + '\n\n[login]\nlogin = {}\npassword = {}'.format(login, password))
    selectAccount(name)
    return True


def getFile(filename):
    local = 'accounts/{}/{}'.format(current_account, filename)
    if current_account and (os.path.isfile(local) or not os.path.isfile('data/' + filename)):
        return local
    return 'data/' + filename


def selectAccount(name):
    global current_account
    current_account = name


def accountExists(name):
    return os.path.isdir('accounts/' + name)


def listAccounts():
    return ', '.join(os.listdir('accounts'))


if not os.path.isdir('accounts'):
    try:
        os.mkdir('accounts')
    except PermissionError:
        print('Unable to create accounts directory')
        sys.exit()
acc = args.args['account']
if acc is None:
    acc = forceInput('Enter account name ({}): '.format(listAccounts() or 'no existing accounts'))

if not validateName(acc):
    print('Invalid account name')
    sys.exit()
if accountExists(acc):
    selectAccount(acc)
else:
    if not listAccounts() or input('Account {} does not exist. Create it? [y/n]'.format(acc)).lower() == 'y':
        print('Creating new account')
        createAccount(acc)
    else:
        sys.exit()
