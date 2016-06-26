import os
import args
import sys

account_files = ['banned.txt', 'captcha.txt', 'noadd.txt', 'token.txt']
current_account = None

def forceInput(text):
    s = ''
    while not s.strip():
        s = input(text)
    return s

def createAccount(name):
    if not name or len(name) > 256 or any(i in name for i in './\\ '):
        return False
    login = forceInput('Login for {}: '.format(name))
    password = forceInput('Password for {}: '.format(name))
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
    if not name or len(name) > 256 or any(i in name for i in './\\ '):
        return False
    return os.path.isdir('accounts/' + name)

def listAccounts():
    return ', '.join(os.listdir('accounts'))

if not os.path.isdir('accounts'):
    os.mkdir('accounts')
acc = args.args['account']
if acc is None:
    acc = forceInput('Enter account name ({}): '.format(listAccounts() or 'no existing accounts'))

if accountExists(acc):
    selectAccount(acc)
else:
    if not listAccounts() or input('Account {} does not exist. Create it? [y/n]'.format(acc)).lower() == 'y':
        print('Creating new account')
        if not createAccount(acc):
            print('Invalid account name')
            sys.exit()
    else:
        sys.exit()
