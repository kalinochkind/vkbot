import getpass
import os
import sys

import args
import pack

account_files = ['captcha.txt', 'token.txt']
current_account = None
default_config = 'inf.cfg.default'
old_dir = os.getcwd()

def abspath(path):
    path = os.path.expanduser(path)
    if os.path.isabs(path):
        return path
    return os.path.join(old_dir, path)

def forceInput(text, password=False):
    s = ''
    while not s.strip():
        try:
            s = getpass.getpass(text) if password else input(text)
        except EOFError:
            print()
            sys.exit()
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
        f.write(open(default_config).read().strip() + '\n\n[login]\nlogin = {}\npassword = {}'.format(login, password))
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

def init():
    if args.args.get('pack'):
        pack.pack(abspath(args.args['pack']))
        sys.exit()
    if args.args.get('pack_data'):
        pack.pack_data(abspath(args.args['pack_data']))
        sys.exit()
    if args.args.get('unpack'):
        pack.unpack(abspath(args.args['unpack']))
        sys.exit()

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
        try:
            if not listAccounts() or input('Account {} does not exist. Create it? [y/n]'.format(acc)).lower() == 'y':
                print('Creating new account')
                createAccount(acc)
            else:
                sys.exit()
        except EOFError:
            print()
            sys.exit()
