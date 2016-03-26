import time
import traceback
import db_logger
import sys
import threading
import os
import accounts

errLock = threading.Lock()

# s = (console message, db message)
def info(s, color=''):
    if isinstance(s, str):
        s = (s, s)
    if color == 'red':
        print('\033[38;5;9m' + s[0] + '\033[0m')
    elif color == 'green':
        print('\033[38;5;10m' + s[0] + '\033[0m')
    elif color == 'yellow':
        print('\033[38;5;11m' + s[0] + '\033[0m')
    elif color:
        print('[{}] {}'.format(color.upper(), s[0]))
    else:
        print(s[0])
    db_logger.log(s[1], color)
    sys.stdout.flush()

def warning(s):
    info(s, 'warning')

def error(s, need_exc_info=False):
    info(s, 'error')
    if not isinstance(s, str):
        s = s[0]
    with errLock:
        write('error', s)
        if need_exc_info:
            with open(logdir + 'error.log', 'a', encoding='utf-8') as f:
                traceback.print_exc(file=f)
                print(file=f)

def fatal(s):
    info(s, 'fatal')
    sys.exit()


datetime_format = '%d.%m.%Y %H:%M:%S'

logdir = 'accounts/{}/logs/'.format(accounts.current_account)
if not os.path.isdir(logdir):
    os.mkdir(logdir)

def write(log, s):
    curtime = time.strftime(datetime_format, time.localtime())
    with open(logdir + log + '.log', 'a', encoding='utf-8') as f:
        f.write('[{}] {}\n'.format(curtime, s))
