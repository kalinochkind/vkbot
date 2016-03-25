import time
import traceback
import db_logger
import sys
import threading
import os
import accounts

errLock = threading.Lock()

def info(s, color=''):
    if color == 'red':
        print('\033[38;5;9m' + s + '\033[0m')
    elif color == 'green':
        print('\033[38;5;10m' + s + '\033[0m')
    elif color == 'yellow':
        print('\033[38;5;11m' + s + '\033[0m')
    else:
        print(s)
        color = ''
    db_logger.log(s, color)
    sys.stdout.flush()

def warning(s):
    print('[WARNING]', s)
    db_logger.log(s, 'warning')
    sys.stdout.flush()

def error(s, need_exc_info=False):
    print('[ERROR]', s)
    db_logger.log(s, 'error')
    with errLock:
        write('error', s)
        if need_exc_info:
            with open(logdir + 'error.log', 'a', encoding='utf-8') as f:
                traceback.print_exc(file=f)
                print(file=f)
    sys.stdout.flush()

def fatal(s):
    print('[FATAL]', s)
    db_logger.log(s, 'fatal')
    sys.stdout.flush()
    exit(0)


datetime_format = '%d.%m.%Y %H:%M:%S'

logdir = 'accounts/{}/logs/'.format(accounts.current_account)
if not os.path.isdir(logdir):
    os.mkdir(logdir)

def write(log, s):
    curtime = time.strftime(datetime_format, time.localtime())
    with open(logdir + log + '.log', 'a', encoding='utf-8') as f:
        f.write('[{}] {}\n'.format(curtime, s))
